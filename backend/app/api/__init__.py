"""HTTP API routers. Handlers stay thin; parameters come from ``app.config``."""

from fastapi import APIRouter

from app.api.circuits import router as circuits_router
from app.api.embodiment import router as embodiment_router
from app.api.escape import router as escape_router
from app.api.health import router as health_router
from app.api.intervention import router as intervention_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(escape_router)
api_router.include_router(circuits_router)
api_router.include_router(embodiment_router)
api_router.include_router(intervention_router)

__all__ = ["api_router"]
