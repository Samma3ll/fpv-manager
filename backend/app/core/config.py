"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://fpv_admin:change_me@postgres:5432/fpv_manager"
    
    # Redis
    redis_url: str = "redis://redis:6379"
    
    # Celery
    celery_broker_url: str = "redis://redis:6379"
    celery_result_backend: str = "redis://redis:6379"
    celery_worker_concurrency: int = 4
    
    # MinIO
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_public_url: str = "http://minio:9000"
    minio_bucket_blackbox_logs: str = "blackbox-logs"
    minio_bucket_assets: str = "assets"
    
    # Security
    secret_key: str = "change-me-in-production-with-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Application
    environment: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
