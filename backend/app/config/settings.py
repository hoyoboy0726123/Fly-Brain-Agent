"""Application settings.

Values are read from environment variables prefixed with ``FLYBRAIN_`` (and from a
``.env`` file in the current working directory, if present). Defaults are safe for
local development and require no dataset to be present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: ``backend/`` directory (this file lives at backend/app/config/settings.py).
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]

#: Repository root, i.e. the parent of ``backend/``.
PROJECT_ROOT: Path = BACKEND_DIR.parent

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime configuration for the FlyBrain Agent backend."""

    model_config = SettingsConfigDict(
        env_prefix="FLYBRAIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FlyBrain Agent"
    environment: Environment = "development"

    # HTTP server
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"

    #: Comma-separated list of origins allowed by CORS (the Vite dev server by default).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Filesystem layout. Raw datasets are never committed (see DATA.md).
    project_root: Path = PROJECT_ROOT
    data_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "data")

    #: Where the MaleCNS v1.0 flat-connectome release files are placed under ``raw_data_dir``.
    #: Mirrors the object prefix in the official bucket ``gs://flyem-male-cns``.
    malecns_raw_subdir: str = "male-cns/v1.0/connectome-data/flat-connectome"

    @property
    def cors_origin_list(self) -> list[str]:
        """``cors_origins`` split into a clean list, ignoring blanks."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def circuits_data_dir(self) -> Path:
        return self.data_dir / "circuits"

    @property
    def malecns_raw_dir(self) -> Path:
        return self.raw_data_dir / self.malecns_raw_subdir

    @property
    def graph_cache_dir(self) -> Path:
        """Memory-mappable ``.npy`` cache of the canonical graph adjacency (git-ignored)."""
        return self.processed_data_dir / "graph_cache"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached after first call)."""
    return Settings()


def clear_settings_cache() -> None:
    """Forget the cached settings so the next ``get_settings()`` re-reads the environment."""
    get_settings.cache_clear()
