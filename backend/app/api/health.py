"""Liveness endpoint used by the frontend and by the smoke test."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import CURRENT_PHASE, SERVICE_NAME, __version__
from app.config import Settings, get_settings
from app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Backend liveness check")
def get_health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=__version__,
        environment=settings.environment,
        phase=CURRENT_PHASE,
    )
