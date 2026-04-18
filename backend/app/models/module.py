"""Module model - registry of available analysis modules."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text

from app.core.database import Base


class Module(Base):
    """
    Module registry for analysis plugins and features.

    Supports dynamic enabling/disabling of analysis modules and future plugins.
    The analysis_task and frontend_route fields allow the backend and frontend
    to discover capabilities at runtime without hardcoding module lists.
    """

    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    module_type = Column(String(50), nullable=False)  # "analysis", "storage", "utility"
    analysis_task = Column(String(255), nullable=True)  # Celery task name, e.g. "analyze_log_step_response"
    frontend_route = Column(String(255), nullable=True)  # Frontend tab/route key, e.g. "step_response"
    config_json = Column(JSON, default=dict, nullable=False)  # Module-specific settings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Module(id={self.id}, name='{self.name}', enabled={self.enabled})>"
