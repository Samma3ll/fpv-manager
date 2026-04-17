"""Drone request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DroneBase(BaseModel):
    """Base schema for Drone with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Drone name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Drone description"
    )
    frame_size: Optional[str] = Field(
        None, max_length=50, description="Frame size (e.g., 5-inch, 7-inch)"
    )
    motor_kv: Optional[int] = Field(None, ge=100, le=100000, description="Motor KV rating")
    prop_size: Optional[str] = Field(None, max_length=50, description="Propeller size")
    weight_g: Optional[float] = Field(None, ge=0, description="Weight in grams")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")


class DroneCreate(DroneBase):
    """Schema for creating a new Drone."""

    pass


class DroneUpdate(BaseModel):
    """Schema for updating a Drone (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    frame_size: Optional[str] = Field(None, max_length=50)
    motor_kv: Optional[int] = Field(None, ge=100, le=100000)
    prop_size: Optional[str] = Field(None, max_length=50)
    weight_g: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)


class DroneResponse(DroneBase):
    """Schema for Drone response (with metadata)."""

    id: int = Field(..., description="Drone unique identifier")
    picture_url: Optional[str] = Field(
        None, description="API URL for drone picture retrieval"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class DroneListResponse(BaseModel):
    """Schema for list of Drones with pagination."""

    items: list[DroneResponse] = Field(..., description="List of drones")
    total: int = Field(..., ge=0, description="Total count of drones")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Number of items returned")
