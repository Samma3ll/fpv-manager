"""BlackboxLog request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import LogStatus


class BlackboxLogBase(BaseModel):
    """Base schema for BlackboxLog."""

    drone_id: int = Field(..., gt=0, description="Drone ID")
    file_name: str = Field(..., min_length=1, max_length=255, description="File name")
    flight_date: Optional[datetime] = Field(None, description="Flight date/time")
    duration_s: Optional[float] = Field(None, ge=0, description="Flight duration in seconds")
    betaflight_version: Optional[str] = Field(None, max_length=50, description="Betaflight version")
    craft_name: Optional[str] = Field(None, max_length=255, description="Craft name from log")
    pid_roll: Optional[float] = Field(None, description="PID roll P value")
    pid_pitch: Optional[float] = Field(None, description="PID pitch P value")
    pid_yaw: Optional[float] = Field(None, description="PID yaw P value")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class BlackboxLogCreate(BlackboxLogBase):
    """Schema for creating a new BlackboxLog."""

    pass


class BlackboxLogUpdate(BaseModel):
    """Schema for updating a BlackboxLog."""

    drone_id: Optional[int] = Field(None, gt=0)
    file_name: Optional[str] = Field(None, min_length=1, max_length=255)
    flight_date: Optional[datetime] = None
    duration_s: Optional[float] = Field(None, ge=0)
    betaflight_version: Optional[str] = Field(None, max_length=50)
    craft_name: Optional[str] = Field(None, max_length=255)
    pid_roll: Optional[float] = None
    pid_pitch: Optional[float] = None
    pid_yaw: Optional[float] = None
    notes: Optional[str] = Field(None, max_length=2000)
    tags: Optional[list[str]] = None
    status: Optional[LogStatus] = None

    @field_validator("tags", mode="before")
    @classmethod
    def reject_null_tags(cls, v):
        """Reject explicit null values for tags."""
        if v is None:
            raise ValueError("tags cannot be null")
        return v


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