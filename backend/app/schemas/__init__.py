"""Pydantic schemas for request/response validation."""

from .drone import DroneCreate, DroneUpdate, DroneResponse, DroneListResponse
from .blackbox_log import (
    BlackboxLogCreate,
    BlackboxLogResponse,
    BlackboxLogListResponse,
    BlackboxLogUpdate,
)
from .module import ModuleResponse, ModuleUpdate, ModuleListResponse

__all__ = [
    "DroneCreate",
    "DroneUpdate",
    "DroneResponse",
    "DroneListResponse",
    "BlackboxLogCreate",
    "BlackboxLogResponse",
    "BlackboxLogListResponse",
    "BlackboxLogUpdate",
    "ModuleResponse",
    "ModuleUpdate",
    "ModuleListResponse",
]
