"""HTTP API routers. Handlers stay thin; parameters come from ``app.config``."""

from fastapi import APIRouter

from app.api.escape import router as escape_router
from app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(escape_router)

__all__ = ["api_router"]
