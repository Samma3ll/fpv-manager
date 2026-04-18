"""Pydantic schemas for Module registry."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    description: str | None = None
    enabled: bool
    module_type: str
    analysis_task: str | None = None
    frontend_route: str | None = None
    config_json: dict = {}
    created_at: datetime


class ModuleUpdate(BaseModel):
    enabled: bool | None = None
    config_json: dict | None = None


class ModuleListResponse(BaseModel):
    items: list[ModuleResponse]
    total: int
