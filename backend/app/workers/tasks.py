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
from app.models import BlackboxLog, LogStatus, Module
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
                logger.info("Successfully loaded and parsed log from temporary file")

                # Extract metadata from headers
                headers = parser.headers
                logger.info("Extracted headers from log")

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


@shared_task(bind=True, name="run_all_analyses", max_retries=3)
def run_all_analyses(self, log_id: int):
    """
    Run all configured analyses for a BlackboxLog and persist their sanitized results.
    
    Downloads the log, builds a parser, loads enabled analysis modules from the
    Module table, runs only enabled analyses, computes tune_score only when that
    module is enabled, replaces any existing LogAnalysis rows for the log with
    newly generated results, and commits.
    
    Parameters:
        log_id (int): Primary key of the BlackboxLog to analyze

    Returns:
        dict: Summary with keys:
            - `log_id`: the analyzed log id
            - `status`: `"success"` or `"error"`
            - on success: `tune_score` (the tune overall_score or 0) and `modules_analyzed`
            - on error: `error` (error message)
    """
    logger.info(f"Starting all analyses for log {log_id}")

    # Map of module name -> (import_path, function_name)
    ANALYSIS_REGISTRY = {
        "step_response": ("app.analysis.step_response", "analyze_step_response"),
        "fft_noise": ("app.analysis.fft_noise", "analyze_fft_noise"),
        "pid_error": ("app.analysis.pid_error", "analyze_pid_error"),
        "motor_analysis": ("app.analysis.motor_analysis", "analyze_motor_output"),
        "gyro_spectrogram": ("app.analysis.gyro_spectrogram", "analyze_gyro_spectrogram"),
    }

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

        # Query enabled analysis modules from the Module table
        enabled_modules = session.execute(
            select(Module).where(Module.enabled == True, Module.module_type == "analysis")  # noqa: E712
        ).scalars().all()
        enabled_names = {m.name for m in enabled_modules}
        logger.info(f"Enabled analysis modules: {enabled_names}")

        try:
            # Download file
            logger.info(f"Downloading log file for analysis: {log_entry.file_path}")
            file_content = minio_client.download_file(
                bucket=minio_client.bucket_blackbox,
                object_name=log_entry.file_path,
            )
            
            # Load parser — use context manager to keep temp file alive
            # during lazy frame iteration across all analysis modules
            from app.analysis.utils import ParserContextManager
            from orangebox import Parser as OrangeboxParser
            parser_ctx = ParserContextManager(file_content)
            parser_ctx.__enter__()
            
            # Helper to create a fresh parser for each module
            # (parser.frames() is a generator exhausted after one iteration)
            def fresh_parser():
                return OrangeboxParser.load(parser_ctx.temp_path)
            
            enabled_module_names = enabled_names

            logger.info(
                "Running enabled analyses for log %s: %s",
                log_id,
                sorted(enabled_module_names),
            )
            
            from app.analysis.step_response import analyze_step_response
            from app.analysis.fft_noise import analyze_fft_noise
            from app.analysis.pid_error import analyze_pid_error
            from app.analysis.motor_analysis import analyze_motor_output
            from app.analysis.gyro_spectrogram import analyze_gyro_spectrogram
            from app.analysis.tune_score import score_tune_quality
            
            analysis_registry = {
                "step_response": lambda: analyze_step_response(fresh_parser()),
                "fft_noise": lambda: analyze_fft_noise(fresh_parser()),
                "pid_error": lambda: analyze_pid_error(fresh_parser()),
                "motor_analysis": lambda: analyze_motor_output(fresh_parser()),
                "gyro_spectrogram": lambda: analyze_gyro_spectrogram(fresh_parser()),
            }

            # Store successful results for prerequisite reuse
            analysis_results = {}

            # Store all results in database
            from app.models import LogAnalysis

            analyses = []
            for module_name, analyzer in analysis_registry.items():
                if module_name not in enabled_module_names:
                    continue

                try:
                    module_result = sanitize_for_json(analyzer())
                    analysis_results[module_name] = module_result
                    analyses.append(
                        LogAnalysis(
                            log_id=log_id,
                            module=module_name,
                            result_json=module_result,
                        )
                    )
                except Exception as module_error:
                    logger.warning(
                        "Analysis module '%s' failed for log %s: %s",
                        module_name,
                        log_id,
                        module_error,
                    )

            tune_score_value = 0
            if "tune_score" in enabled_module_names:
                try:
                    tune_score_result = score_tune_quality(
                        analysis_results.get("step_response", {}),
                        analysis_results.get("fft_noise", {}),
                        analysis_results.get("pid_error", {}),
                        analysis_results.get("motor_analysis", {}),
                    )
                    tune_score_result = sanitize_for_json(tune_score_result)
                    analyses.append(
                        LogAnalysis(
                            log_id=log_id,
                            module="tune_score",
                            result_json=tune_score_result,
                        )
                    )
                    if isinstance(tune_score_result, dict):
                        tune_score_value = tune_score_result.get("overall_score", 0)
                    else:
                        logger.warning(
                            "Analysis module 'tune_score' returned unexpected type %s for log %s",
                            type(tune_score_result).__name__,
                            log_id,
                        )
                except Exception as module_error:
                    logger.warning(
                        "Analysis module 'tune_score' failed for log %s: %s",
                        log_id,
                        module_error,
                    )
            
            # Delete any existing analyses for this log
            session.query(LogAnalysis).filter(LogAnalysis.log_id == log_id).delete()
            
            for module_name, raw_result in analysis_results.items():
                sanitized = sanitize_for_json(raw_result)
                session.add(LogAnalysis(
                    log_id=log_id,
                    module=module_name,
                    result_json=sanitized,
                ))

            session.commit()
            logger.info(f"Stored {len(analysis_results)} analyses for log {log_id}")
            
            return {
                "log_id": log_id,
                "status": "success",
                "tune_score": tune_score_value,
                "modules_analyzed": len(analyses),
            }
            
        except Exception as e:
            logger.error(f"Error running analyses for log {log_id}: {e}", exc_info=True)

            # Roll back session
            try:
                session.rollback()
            except Exception as rollback_error:
                logger.error(f"Failed to rollback session: {rollback_error}")

            # Update log status to analysis error
            try:
                result = session.execute(
                    select(BlackboxLog).where(BlackboxLog.id == log_id)
                )
                log_entry = result.scalar_one_or_none()
                if log_entry:
                    log_entry.error_message = f"Analysis failed: {str(e)[:255]}"
                    session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update log error status: {update_error}")

            # Retry with exponential backoff
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

        finally:
            # Clean up parser temp file
            try:
                parser_ctx.__exit__(None, None, None)
            except Exception:
                pass


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
            from sqlalchemy import delete

            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_step_response(parser)

            # Delete existing analysis for this module
            session.execute(
                delete(LogAnalysis).where(
                    LogAnalysis.log_id == log_id,
                    LogAnalysis.module == "step_response"
                )
            )

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
            from sqlalchemy import delete

            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_fft_noise(parser)

            # Delete existing analysis for this module
            session.execute(
                delete(LogAnalysis).where(
                    LogAnalysis.log_id == log_id,
                    LogAnalysis.module == "fft_noise"
                )
            )

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
            from sqlalchemy import delete

            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_pid_error(parser)

            # Delete existing analysis for this module
            session.execute(
                delete(LogAnalysis).where(
                    LogAnalysis.log_id == log_id,
                    LogAnalysis.module == "pid_error"
                )
            )

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
            from sqlalchemy import delete

            parser = load_parser_from_file_content(file_content)
            analysis_result = analyze_motor_output(parser)

            # Delete existing analysis for this module
            session.execute(
                delete(LogAnalysis).where(
                    LogAnalysis.log_id == log_id,
                    LogAnalysis.module == "motor_analysis"
                )
            )

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
