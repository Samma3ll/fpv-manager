"""API v1 routers."""

from fastapi import APIRouter

from .drones import router as drones_router
from .logs import router as logs_router

router = APIRouter(prefix="/v1")
router.include_router(drones_router)
router.include_router(logs_router)

__all__ = ["router"]
