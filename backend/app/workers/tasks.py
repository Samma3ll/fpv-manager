"""Celery task definitions for async processing."""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="test_task")
def test_task(self, x: int, y: int) -> int:
    """Test task for Celery setup verification."""
    logger.info(f"Executing test_task: {x} + {y}")
    return x + y


@shared_task(bind=True, name="parse_blackbox_log")
def parse_blackbox_log(self, log_id: int):
    """
    Parse a Betaflight blackbox log file.
    
    This is a placeholder for Phase 4.
    In production, this will:
    1. Download log from MinIO
    2. Parse with orangebox
    3. Extract headers and time-series data
    4. Store as Parquet
    5. Update log status to 'ready'
    """
    logger.info(f"Placeholder: Parsing log {log_id}")
    # TODO: Implement in Phase 4
    return {"log_id": log_id, "status": "placeholder"}


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
