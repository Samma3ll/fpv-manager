"""BlackboxLog request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import LogStatus


class BlackboxLogBase(BaseModel):
    """Base schema for BlackboxLog."""

    drone_id: int = Field(..., gt=0, description="Drone ID")
    file_name: str = Field(..., min_length=1, max_length=500, description="File name")
    flight_date: Optional[datetime] = Field(None, description="Flight date/time")
    duration_s: Optional[float] = Field(None, ge=0, description="Flight duration in seconds")
    betaflight_version: Optional[str] = Field(None, max_length=50, description="Betaflight version")
    craft_name: Optional[str] = Field(None, max_length=255, description="Craft name from log")
    pid_roll: Optional[dict] = Field(None, description="PID values for roll")
    pid_pitch: Optional[dict] = Field(None, description="PID values for pitch")
    pid_yaw: Optional[dict] = Field(None, description="PID values for yaw")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")
    tags: Optional[list[str]] = Field(None, description="Tags for categorization")


class BlackboxLogCreate(BlackboxLogBase):
    """Schema for creating a new BlackboxLog."""

    pass


class BlackboxLogUpdate(BaseModel):
    """Schema for updating a BlackboxLog."""

    drone_id: Optional[int] = Field(None, gt=0)
    file_name: Optional[str] = Field(None, min_length=1, max_length=500)
    flight_date: Optional[datetime] = None
    duration_s: Optional[float] = Field(None, ge=0)
    betaflight_version: Optional[str] = Field(None, max_length=50)
    craft_name: Optional[str] = Field(None, max_length=255)
    pid_roll: Optional[dict] = None
    pid_pitch: Optional[dict] = None
    pid_yaw: Optional[dict] = None
    notes: Optional[str] = Field(None, max_length=2000)
    tags: Optional[list[str]] = None
    status: Optional[LogStatus] = None


class BlackboxLogResponse(BlackboxLogBase):
    """Schema for BlackboxLog response."""

    id: int = Field(..., description="Log unique identifier")
    file_path: Optional[str] = Field(None, description="File path in storage")
    status: LogStatus = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    log_index: Optional[int] = Field(None, description="Log index in file")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class BlackboxLogListResponse(BaseModel):
    """Schema for list of BlackboxLogs with pagination."""

    items: list[BlackboxLogResponse] = Field(..., description="List of logs")
    total: int = Field(..., ge=0, description="Total count of logs")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Number of items returned")
