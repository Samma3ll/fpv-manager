"""Module model - registry of available analysis modules."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text

from app.core.database import Base


class Module(Base):
    """
    Module registry for analysis plugins and features.
    
    This table allows dynamic enabling/disabling of analysis modules and other features,
    supporting the modular architecture described in Phase 7.
    
    Attributes:
        id: Unique identifier
        name: Module machine name (e.g., "step_response", "fft_noise", "video", "betaflight_backup")
        display_name: Human-readable name (e.g., "Step Response Analysis")
        description: Description of what the module does
        enabled: Whether the module is active
        module_type: Type of module (e.g., "analysis", "storage", "utility")
        config_json: Module-specific configuration options
        created_at: Timestamp
    """

    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    module_type = Column(String(50), nullable=False)  # "analysis", "storage", "utility"
    config_json = Column(JSON, default=dict, nullable=False)  # Module-specific settings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Module(id={self.id}, name='{self.name}', enabled={self.enabled})>"
