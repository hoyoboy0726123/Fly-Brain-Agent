from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT, Settings, clear_settings_cache, get_settings


def test_defaults_are_local_development() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_project_root_points_at_repository() -> None:
    assert (PROJECT_ROOT / "backend" / "app").is_dir()
    assert (PROJECT_ROOT / "TASKS.md").is_file()


def test_data_directories_follow_sdd_layout() -> None:
    settings = Settings(_env_file=None)
    assert settings.data_dir == PROJECT_ROOT / "data"
    assert settings.raw_data_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.processed_data_dir == PROJECT_ROOT / "data" / "processed"
    assert settings.circuits_data_dir == PROJECT_ROOT / "data" / "circuits"
    # Skeleton folders exist in the repository (kept via .gitkeep).
    skeleton_dirs = (
        settings.raw_data_dir,
        settings.processed_data_dir,
        settings.circuits_data_dir,
    )
    for directory in skeleton_dirs:
        assert directory.is_dir(), directory


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLYBRAIN_ENVIRONMENT", "production")
    monkeypatch.setenv("FLYBRAIN_PORT", "9001")
    monkeypatch.setenv("FLYBRAIN_CORS_ORIGINS", " http://a.example ,http://b.example,, ")
    monkeypatch.setenv("FLYBRAIN_DATA_DIR", "/tmp/flybrain-data")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.port == 9001
    assert settings.cors_origin_list == ["http://a.example", "http://b.example"]
    assert settings.data_dir == Path("/tmp/flybrain-data")
    assert settings.raw_data_dir == Path("/tmp/flybrain-data/raw")


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLYBRAIN_ENVIRONMENT", "staging")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLYBRAIN_PORT", "70000")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached_until_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert get_settings() is first

    monkeypatch.setenv("FLYBRAIN_PORT", "9002")
    assert get_settings() is first  # still cached

    clear_settings_cache()
    assert get_settings().port == 9002
