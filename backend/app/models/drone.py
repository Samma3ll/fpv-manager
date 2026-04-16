"""Drone model - represents a quadcopter or aircraft."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Drone(Base):
    """
    Drone model representing a quadcopter or aircraft.

    Attributes:
        id: Unique identifier
        name: Drone name/identifier (e.g., "Racing Quad #1")
        description: Detailed description of the drone
        frame_size: String-based frame size descriptor (e.g., "3-inch", "5-inch", "5mm")
        motor_kv: Integer motor KV rating (e.g., 2300)
        prop_size: String-based propeller size descriptor (e.g., "3-inch", "5-inch", "5mm")
        weight_g: Weight in grams
        notes: Additional notes about the drone
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """

    __tablename__ = "drones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    frame_size = Column(String(50), nullable=True)  # e.g., "3-inch", "5-inch", "5mm"
    motor_kv = Column(Integer, nullable=True)  # KV rating
    prop_size = Column(String(50), nullable=True)  # e.g., "5-inch", "6-inch"
    weight_g = Column(Float, nullable=True)  # grams
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    blackbox_logs = relationship("BlackboxLog", back_populates="drone", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Drone(id={self.id}, name='{self.name}')>"