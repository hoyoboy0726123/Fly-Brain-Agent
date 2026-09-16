"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.api.circuits import CircuitCatalog
from app.api.escape import EscapeServiceHolder
from app.config import Settings, get_settings

DESCRIPTION = (
    "Connectome-grounded simulation API. Structural connectivity comes from a biological "
    "dataset; any neural activity served by this API is simulated, not measured."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    ``settings`` may be supplied explicitly (e.g. in tests). When it is, the same instance
    is injected into route handlers through the ``get_settings`` dependency.
    """
    resolved = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        # Load the escape demo (config + hash-verified circuit) once at startup; a failure
        # is logged and reported by the escape endpoints as 503, never hidden.
        application.state.escape.warm_up()
        yield

    application = FastAPI(
        title=resolved.app_name,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    application.state.escape = EscapeServiceHolder(resolved)
    application.state.circuits = CircuitCatalog(resolved)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)

    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: resolved

    return application


app = create_app()
