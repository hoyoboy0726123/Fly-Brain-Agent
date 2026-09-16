"""Shared pytest fixtures. No dataset is required by any P0 test."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, clear_settings_cache
from app.main import create_app


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    """Make sure no test observes settings cached by another test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def test_settings() -> Settings:
    """Deterministic settings that ignore any developer ``.env`` file."""
    return Settings(_env_file=None, environment="test")


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
