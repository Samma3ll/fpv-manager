"""Celery application configuration."""

from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "fpv_manager",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_worker_concurrency,
)

# Auto-discover tasks from all registered apps
celery_app.autodiscover_tasks(["app.workers.tasks"])
