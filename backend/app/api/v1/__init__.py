"""API v1 routers."""

from fastapi import APIRouter

from .drones import router as drones_router
from .logs import router as logs_router
from .modules import router as modules_router

router = APIRouter(prefix="/v1")
router.include_router(drones_router)
router.include_router(logs_router)
router.include_router(modules_router)

__all__ = ["router"]
