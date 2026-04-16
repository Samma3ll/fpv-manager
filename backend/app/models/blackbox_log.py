"""BlackboxLog model - represents a Betaflight blackbox log file."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Enum,
    JSON,
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class LogStatus(str, enum.Enum):
    """Log processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class BlackboxLog(Base):
    """
    BlackboxLog model representing a Betaflight blackbox recording.
    
    Attributes:
        id: Unique identifier
        drone_id: Foreign key to Drone
        file_name: Original file name (e.g., "LOG00123.BFL")
        file_path: Path in MinIO (e.g., "blackbox-logs/drone-1/LOG00123.BBL")
        flight_date: Date of flight
        duration_s: Duration of log in seconds
        log_index: Index for multi-log BBL files (0-based)
        betaflight_version: Betaflight firmware version (extracted from header)
        craft_name: Craft name from log header
        pid_roll: Roll PID P value (from header)
        pid_pitch: Pitch PID P value (from header)
        pid_yaw: Yaw PID P value (from header)
        notes: User notes
        tags: JSON array of tags for filtering
        status: Processing status (pending/processing/ready/error)
        error_message: Error message if status is error
        created_at: Timestamp of upload
    """

    __tablename__ = "blackbox_logs"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(Integer, ForeignKey("drones.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False, unique=True)  # MinIO key
    flight_date = Column(DateTime, nullable=True, index=True)
    duration_s = Column(Float, nullable=True)  # seconds
    log_index = Column(Integer, default=0)  # For multi-log BBL files
    betaflight_version = Column(String(50), nullable=True)
    craft_name = Column(String(255), nullable=True)
    pid_roll = Column(Float, nullable=True)
    pid_pitch = Column(Float, nullable=True)
    pid_yaw = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list, nullable=False)  # ["racing", "tuning_experiment"]
    status = Column(Enum(LogStatus), default=LogStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    drone = relationship("Drone", back_populates="blackbox_logs")
    analyses = relationship("LogAnalysis", back_populates="log", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BlackboxLog(id={self.id}, drone_id={self.drone_id}, file_name='{self.file_name}', status={self.status})>"
