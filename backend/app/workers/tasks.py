"""Celery task definitions for async processing."""

from celery import shared_task
from datetime import datetime
import logging
from io import BytesIO
import tempfile
import os
import json
import math

from app.core.database import get_sync_session_factory
from app.core.minio import minio_client
from app.models import BlackboxLog, LogStatus
from sqlalchemy import select

logger = logging.getLogger(__name__)


def sanitize_for_json(obj):
    """
    Recursively convert Python values into JSON-safe structures.
    
    Replaces `NaN`, `Infinity`, and `-Infinity` floats with `None`, and recursively sanitizes values inside dicts, lists, and tuples; other values are returned unchanged.
    
    Parameters:
        obj: The value to sanitize. May be a float, dict, list, tuple, or any other Python value.
    
    Returns:
        The sanitized value: `None` for `NaN`/`Inf`/`-Inf` floats, a dict or list with sanitized contents for containers, or the original value for other types.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    else:
        return obj


@shared_task(bind=True, name="test_task")
def test_task(self, x: int, y: int) -> int:
    """
    Compute the sum of two integers.
    
    Parameters:
        x (int): First addend.
        y (int): Second addend.
    
    Returns:
        int: Sum of `x` and `y`.
    """
    logger.info(f"Executing test_task: {x} + {y}")
    return x + y


@shared_task(bind=True, name="parse_blackbox_log", max_retries=3)
def parse_blackbox_log(self, log_id: int):
    """
    Parse a Betaflight blackbox log, update its BlackboxLog record, and return a summary of the parsing outcome.

    This task downloads the log file from MinIO, parses it with the orangebox Parser, extracts header metadata (Betaflight firmware revision, craft name, and the first P value from roll/pitch/yaw PID arrays when present), attempts to compute flight duration from frame time data, and persists extracted fields to the database. The task transitions the BlackboxLog.status through PROCESSING to READY on success or to ERROR on failure, and writes an error message into BlackboxLog.error_message when parsing fails. On unexpected outer errors the task will trigger Celery retry logic.

    Parameters:
        log_id (int): Primary key of the BlackboxLog row to parse.

    Returns:
        dict: A result summary containing at least the keys:
            - "log_id": the provided `log_id`
            - "status": final status value stored on the BlackboxLog
            - "craft_name": extracted craft name or `None`
            - "betaflight_version": extracted firmware revision or `None`
    """
    logger.info(f"Starting to parse log {log_id}")

    # Get synchronous database session
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        # Fetch log entry
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()

        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error", "message": "Log entry not found"}

        try:
            # Update status to processing
            log_entry.status = LogStatus.PROCESSING
            session.commit()
            logger.info(f"Updated log {log_id} status to PROCESSING")

            # Download file from MinIO
            logger.info(f"Downloading file from MinIO: {log_entry.file_path}")
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            logger.info(f"Downloaded file from MinIO: {log_entry.file_path} ({len(file_content)} bytes)")

            # Parse with orangebox using a temporary file
            temp_file = None
            try:
                from orangebox import Parser

                logger.info(f"Parsing blackbox log {log_entry.file_path}")
                
                # Write to temporary file (Parser.load() expects a file path, not BytesIO)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.bbl') as tmp:
                    tmp.write(file_content)
                    temp_file = tmp.name
                
                logger.info(f"Created temporary file for parsing: {temp_file}")
                parser = Parser.load(temp_file)
                logger.info(f"Successfully loaded and parsed log from temporary file")

                # Extract metadata from headers
                headers = parser.headers
                logger.info(f"Extracted headers from log")

                # Extract firmware version and craft name
                log_entry.betaflight_version = headers.get("Firmware revision", None)
                log_entry.craft_name = headers.get("Craft name", None)
                if not log_entry.craft_name:
                    log_entry.craft_name = None  # Convert empty string to None

                # Extract PID values (format: [P, I, D])
                roll_pid = headers.get("rollPID", None)
                if roll_pid and isinstance(roll_pid, (list, tuple)) and len(roll_pid) > 0:
                    log_entry.pid_roll = float(roll_pid[0])

                pitch_pid = headers.get("pitchPID", None)
                if pitch_pid and isinstance(pitch_pid, (list, tuple)) and len(pitch_pid) > 0:
                    log_entry.pid_pitch = float(pitch_pid[0])

                yaw_pid = headers.get("yawPID", None)
                if yaw_pid and isinstance(yaw_pid, (list, tuple)) and len(yaw_pid) > 0:
                    log_entry.pid_yaw = float(yaw_pid[0])

                logger.info(f"Extracted PIDs - Roll: {log_entry.pid_roll}, Pitch: {log_entry.pid_pitch}, Yaw: {log_entry.pid_yaw}")

                # Calculate flight duration from frame time data
                try:
                    # Find time field index
                    time_idx = None
                    if 'time' in parser.field_names:
                        time_idx = parser.field_names.index('time')

                    if time_idx is not None:
                        # Iterate through frames without materializing the full list
                        first_time = None
                        last_time = None
                        frame_count = 0

                        for frame in parser.frames():
                            frame_count += 1
                            time_value = frame.data[time_idx]

                            if first_time is None:
                                first_time = time_value
                            last_time = time_value

                        if first_time is not None and last_time is not None:
                            if isinstance(last_time, (int, float)) and isinstance(first_time, (int, float)):
                                duration_us = last_time - first_time
                                if duration_us > 0:
                                    log_entry.duration_s = duration_us / 1_000_000  # Convert microseconds to seconds
                                    logger.info(f"Calculated duration: {log_entry.duration_s:.2f}s from {frame_count} frames")
                    else:
                        logger.warning("No 'time' field found in frame data")
                except Exception as e:
                    logger.warning(f"Could not extract duration from frames: {e}")

                # Mark as ready
                log_entry.status = LogStatus.READY
                logger.info(f"Successfully parsed log {log_id}, marking as READY")
            
            except ImportError:
                logger.error("orangebox library not found")
                log_entry.status = LogStatus.ERROR
                log_entry.error_message = "orangebox library not available"
            except Exception as e:
                logger.error(f"Failed to parse log {log_id}: {e}")
                log_entry.status = LogStatus.ERROR
                log_entry.error_message = f"Parse failed: {str(e)[:255]}"
            finally:
                # Clean up temporary file
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.info(f"Cleaned up temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

            # Save changes
            session.commit()
            logger.info(f"Updated log {log_id} in database")
            
            # Trigger analyses if parsing was successful
            if log_entry.status == LogStatus.READY:
                logger.info(f"Triggering analyses for log {log_id}")
                run_all_analyses.apply_async(args=[log_id], countdown=5)

            return {
                "log_id": log_id,
                "status": log_entry.status,
                "craft_name": log_entry.craft_name,
                "betaflight_version": log_entry.betaflight_version,
            }

        except Exception as e:
            logger.error(f"Unexpected error parsing log {log_id}: {e}")
            try:
                log_entry.status = LogStatus.ERROR
                log_entry.error_message = f"Unexpected error: {str(e)[:255]}"
                session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update error status: {db_error}")

            # Retry the task
            raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, name="run_all_analyses")
def run_all_analyses(self, log_id: int):
    """
    Run all configured analyses for a BlackboxLog and persist their sanitized results.
    
    Downloads the log, builds a parser, runs step response, FFT noise, PID error, and motor analyses, computes an overall tune score, replaces any existing LogAnalysis rows for the log with the five analysis results (step_response, fft_noise, pid_error, motor_analysis, tune_score), and commits the results.
    
    Parameters:
        log_id (int): Primary key of the BlackboxLog to analyze
    
    Returns:
        dict: Summary with keys:
            - `log_id`: the analyzed log id
            - `status`: `"success"` or `"error"`
            - on success: `tune_score` (the tune overall_score or 0) and `modules_analyzed` (5)
            - on error: `error` (error message)
    """
    logger.info(f"Starting all analyses for log {log_id}")
    
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        # Fetch log entry
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()
        
        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error", "message": "Log entry not found"}
        
        try:
            # Download file
            logger.info(f"Downloading log file for analysis: {log_entry.file_path}")
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            # Load parser
            from app.analysis.utils import load_parser_from_file_content
            parser = load_parser_from_file_content(file_content)
            
            # Run all analyses
            logger.info(f"Running all analyses for log {log_id}")
            
            from app.analysis.step_response import analyze_step_response
            from app.analysis.fft_noise import analyze_fft_noise
            from app.analysis.pid_error import analyze_pid_error
            from app.analysis.motor_analysis import analyze_motor_output
            from app.analysis.tune_score import score_tune_quality
            
            step_response_result = analyze_step_response(parser)
            fft_result = analyze_fft_noise(parser)
            pid_error_result = analyze_pid_error(parser)
            motor_result = analyze_motor_output(parser)
            
            # Calculate tune score
            tune_score = score_tune_quality(
                step_response_result,
                fft_result,
                pid_error_result,
                motor_result,
            )
            
            # Sanitize all results to remove NaN/Inf values
            step_response_result = sanitize_for_json(step_response_result)
            fft_result = sanitize_for_json(fft_result)
            pid_error_result = sanitize_for_json(pid_error_result)
            motor_result = sanitize_for_json(motor_result)
            tune_score = sanitize_for_json(tune_score)
            
            # Store all results in database
            from app.models import LogAnalysis
            
            analyses = [
                LogAnalysis(
                    log_id=log_id,
                    module="step_response",
                    result_json=step_response_result,
                ),
                LogAnalysis(
                    log_id=log_id,
                    module="fft_noise",
                    result_json=fft_result,
                ),
                LogAnalysis(
                    log_id=log_id,
                    module="pid_error",
                    result_json=pid_error_result,
                ),
                LogAnalysis(
                    log_id=log_id,
                    module="motor_analysis",
                    result_json=motor_result,
                ),
                LogAnalysis(
                    log_id=log_id,
                    module="tune_score",
                    result_json=tune_score,
                ),
            ]
            
            # Delete any existing analyses for this log
            session.query(LogAnalysis).filter(LogAnalysis.log_id == log_id).delete()
            
            # Add new analyses
            for analysis in analyses:
                session.add(analysis)
            
            session.commit()
            logger.info(f"Stored all analyses for log {log_id}")
            
            return {
                "log_id": log_id,
                "status": "success",
                "tune_score": tune_score.get("overall_score", 0),
                "modules_analyzed": 5,
            }
            
        except Exception as e:
            logger.error(f"Error running analyses for log {log_id}: {e}", exc_info=True)
            return {
                "log_id": log_id,
                "status": "error",
                "error": str(e),
            }


@shared_task(bind=True, name="analyze_log_step_response")
def analyze_log_step_response(self, log_id: int):
    """
    Run step-response analysis for a BlackboxLog and persist the result.
    
    Downloads the log file for the given BlackboxLog id, constructs a parser, runs the step-response analysis, stores the analysis output in the LogAnalysis table under module "step_response", and returns a summary of the operation.
    
    Parameters:
        log_id (int): ID of the BlackboxLog to analyze.
    
    Returns:
        dict: Summary containing at minimum `log_id`, `module` ("step_response"), and `status` ("success" or "error"). On error, includes an `error` string with the exception message.
    """
    logger.info(f"Analyzing step response for log {log_id}")
    
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()
        
        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error"}
        
        try:
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            from app.analysis.utils import load_parser_from_file_content
            from app.analysis.step_response import analyze_step_response
            from app.models import LogAnalysis
            
            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_step_response(parser)
            
            # Store result
            analysis = LogAnalysis(
                log_id=log_id,
                module="step_response",
                result_json=analysis_result,
            )
            session.add(analysis)
            session.commit()
            
            return {
                "log_id": log_id,
                "module": "step_response",
                "status": "success",
            }
        except Exception as e:
            logger.error(f"Error analyzing step response for log {log_id}: {e}")
            return {
                "log_id": log_id,
                "module": "step_response",
                "status": "error",
                "error": str(e),
            }


@shared_task(bind=True, name="analyze_log_fft")
def analyze_log_fft(self, log_id: int):
    """
    Run FFT noise analysis for the specified blackbox log and persist the result.
    
    Returns:
        dict: Summary of the operation containing:
            - `log_id` (int): The analyzed log id.
            - `module` (str): The module name `"fft_noise"`.
            - `status` (str): `"success"` when stored, `"error"` on failure.
            - `error` (str, optional): Error message present when `status` is `"error"`.
    """
    logger.info(f"Analyzing FFT for log {log_id}")
    
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()
        
        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error"}
        
        try:
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            from app.analysis.utils import load_parser_from_file_content
            from app.analysis.fft_noise import analyze_fft_noise
            from app.models import LogAnalysis
            
            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_fft_noise(parser)
            
            # Store result
            analysis = LogAnalysis(
                log_id=log_id,
                module="fft_noise",
                result_json=analysis_result,
            )
            session.add(analysis)
            session.commit()
            
            return {
                "log_id": log_id,
                "module": "fft_noise",
                "status": "success",
            }
        except Exception as e:
            logger.error(f"Error analyzing FFT for log {log_id}: {e}")
            return {
                "log_id": log_id,
                "module": "fft_noise",
                "status": "error",
                "error": str(e),
            }


@shared_task(bind=True, name="analyze_log_pid_error")
def analyze_log_pid_error(self, log_id: int):
    """
    Run PID error analysis for the blackbox log identified by log_id and persist the result as a LogAnalysis row.
    
    Parameters:
        log_id (int): ID of the BlackboxLog to analyze.
    
    Returns:
        dict: Summary including `log_id`, `module` (set to `"pid_error"`), and `status` (`"success"` or `"error"`). On error includes an `error` key with the exception message.
    """
    logger.info(f"Analyzing PID error for log {log_id}")
    
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()
        
        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error"}
        
        try:
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            from app.analysis.utils import load_parser_from_file_content
            from app.analysis.pid_error import analyze_pid_error
            from app.models import LogAnalysis
            
            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_pid_error(parser)
            
            # Store result
            analysis = LogAnalysis(
                log_id=log_id,
                module="pid_error",
                result_json=analysis_result,
            )
            session.add(analysis)
            session.commit()
            
            return {
                "log_id": log_id,
                "module": "pid_error",
                "status": "success",
            }
        except Exception as e:
            logger.error(f"Error analyzing PID error for log {log_id}: {e}")
            return {
                "log_id": log_id,
                "module": "pid_error",
                "status": "error",
                "error": str(e),
            }


@shared_task(bind=True, name="analyze_log_motor")
def analyze_log_motor(self, log_id: int):
    """
    Run motor-output analysis for a blackbox log and persist the result.
    
    Downloads the log file, constructs a parser, executes the motor-output analysis, and stores the analysis JSON in the `LogAnalysis` table with module name `"motor_analysis"`.
    
    Parameters:
        log_id (int): Primary key of the BlackboxLog entry to analyze.
    
    Returns:
        dict: On success: `{"log_id": log_id, "module": "motor_analysis", "status": "success"}`.
              If the log entry is not found: `{"log_id": log_id, "status": "error"}`.
              On analysis or storage failure: `{"log_id": log_id, "module": "motor_analysis", "status": "error", "error": <error message>}`.
    """
    logger.info(f"Analyzing motor output for log {log_id}")
    
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        result = session.execute(
            select(BlackboxLog).where(BlackboxLog.id == log_id)
        )
        log_entry = result.scalar_one_or_none()
        
        if not log_entry:
            logger.error(f"Log entry {log_id} not found")
            return {"log_id": log_id, "status": "error"}
        
        try:
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            from app.analysis.utils import load_parser_from_file_content
            from app.analysis.motor_analysis import analyze_motor_output
            from app.models import LogAnalysis
            
            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_motor_output(parser)
            
            # Store result
            analysis = LogAnalysis(
                log_id=log_id,
                module="motor_analysis",
                result_json=analysis_result,
            )
            session.add(analysis)
            session.commit()
            
            return {
                "log_id": log_id,
                "module": "motor_analysis",
                "status": "success",
            }
        except Exception as e:
            logger.error(f"Error analyzing motor output for log {log_id}: {e}")
            return {
                "log_id": log_id,
                "module": "motor_analysis",
                "status": "error",
                "error": str(e),
            }