"""Celery task definitions for async processing."""

from celery import shared_task
from datetime import datetime
import logging
from io import BytesIO

from app.core.database import get_sync_session_factory
from app.core.minio import minio_client
from app.models import BlackboxLog, LogStatus
from sqlalchemy import select

logger = logging.getLogger(__name__)


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

            # Parse with orangebox
            try:
                from orangebox import Parser

                logger.info(f"Parsing blackbox log {log_entry.file_path}")
                parser = Parser.load(BytesIO(file_content))

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

            # Save changes
            session.commit()
            logger.info(f"Updated log {log_id} in database")

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


@shared_task(bind=True, name="analyze_log_step_response")
def analyze_log_step_response(self, log_id: int):
    """Analyze step response from a blackbox log. (Placeholder for Phase 5)"""
    logger.info(f"Placeholder: Analyzing step response for log {log_id}")
    # TODO: Implement in Phase 5
    return {"log_id": log_id, "module": "step_response", "status": "placeholder"}


@shared_task(bind=True, name="analyze_log_fft")
def analyze_log_fft(self, log_id: int):
    """Analyze FFT noise from a blackbox log. (Placeholder for Phase 5)"""
    logger.info(f"Placeholder: Analyzing FFT for log {log_id}")
    # TODO: Implement in Phase 5
    return {"log_id": log_id, "module": "fft_noise", "status": "placeholder"}