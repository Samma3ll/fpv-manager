"""Celery task definitions for async processing."""

from celery import shared_task
from datetime import datetime
import logging
from io import BytesIO
import asyncio

from app.core.database import get_session_factory
from app.core.minio import minio_client
from app.models import BlackboxLog, LogStatus
from sqlalchemy import select

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="test_task")
def test_task(self, x: int, y: int) -> int:
    """Test task for Celery setup verification."""
    logger.info(f"Executing test_task: {x} + {y}")
    return x + y


@shared_task(bind=True, name="parse_blackbox_log", max_retries=3)
def parse_blackbox_log(self, log_id: int):
    """
    Parse a Betaflight blackbox log file.
    
    This task:
    1. Downloads log from MinIO
    2. Parses with orangebox
    3. Extracts headers and metadata
    4. Updates log entry with parsed data
    5. Sets status to 'ready' or 'error'
    """
    logger.info(f"Starting to parse log {log_id}")
    
    # Get database session
    async def _parse_and_update():
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Fetch log entry
            result = await session.execute(
                select(BlackboxLog).where(BlackboxLog.id == log_id)
            )
            log_entry = result.scalar_one_or_none()
            
            if not log_entry:
                logger.error(f"Log entry {log_id} not found")
                return {"log_id": log_id, "status": "error", "message": "Log entry not found"}
            
            try:
                # Update status to processing
                log_entry.status = LogStatus.PROCESSING
                await session.commit()
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
                        frames = list(parser.frames())
                        if len(frames) >= 2:
                            # Find time field index
                            time_idx = parser.field_names.index('time') if 'time' in parser.field_names else None
                            
                            if time_idx is not None:
                                # Access frame data by index (frames are tuples)
                                start_time = frames[0].data[time_idx]
                                end_time = frames[-1].data[time_idx]
                                
                                if isinstance(end_time, (int, float)) and isinstance(start_time, (int, float)):
                                    duration_us = end_time - start_time
                                    if duration_us > 0:
                                        log_entry.duration_s = duration_us / 1_000_000  # Convert microseconds to seconds
                                        logger.info(f"Calculated duration: {log_entry.duration_s:.2f}s from {len(frames)} frames")
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
                await session.commit()
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
                    await session.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update error status: {db_error}")
                
                # Retry the task
                raise self.retry(exc=e, countdown=60)
    
    # Run async function
    result = asyncio.run(_parse_and_update())
    return result


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
