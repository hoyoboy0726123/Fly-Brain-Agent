"""Startup validation of the one-command launcher (``scripts/run_demo.py``)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "run_demo.py"


@pytest.fixture(scope="module")
def run_demo():
    spec = importlib.util.spec_from_file_location("run_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["run_demo"] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_frontend(tmp_path: Path) -> Path:
    frontend = tmp_path / "frontend"
    for name in ("vite", "react", "react-dom", "d3-force", "d3-zoom", "d3-selection"):
        package = frontend / "node_modules" / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": name}))
    return frontend


def test_ready_when_artifact_and_dependencies_are_present(run_demo, fake_frontend: Path) -> None:
    settings = Settings(_env_file=None, environment="test")
    assert run_demo.validate(fake_frontend, settings) == []


def test_missing_circuit_artifact_is_reported_with_a_fix(
    run_demo, fake_frontend: Path, tmp_path: Path
) -> None:
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path / "data")
    problems = run_demo.validate(fake_frontend, settings)
    assert len(problems) == 1
    assert "escape_v1 circuit artifact is missing" in problems[0].title
    assert "make build-escape-config" in problems[0].fix and "git checkout" in problems[0].fix
    rendered = problems[0].render()
    assert "Run:" in rendered


def test_tampered_artifact_is_rejected(run_demo, fake_frontend: Path, tmp_path: Path) -> None:
    source = Settings(_env_file=None).circuits_data_dir / "escape_v1.json"
    payload = json.loads(source.read_text())
    payload["edges"][0]["synapse_count"] += 1
    circuits = tmp_path / "data" / "circuits"
    circuits.mkdir(parents=True)
    (circuits / "escape_v1.json").write_text(json.dumps(payload))
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path / "data")
    problems = run_demo.validate(fake_frontend, settings)
    assert len(problems) == 1
    assert "integrity" in problems[0].title.lower() or "hash" in problems[0].title.lower()


def test_hash_mismatch_with_config_is_rejected(
    run_demo, fake_frontend: Path, tmp_path: Path
) -> None:
    from app.behavior import load_escape_config

    config = load_escape_config("escape_v1").model_copy(update={"expected_circuit_hash": "0" * 64})
    config_path = tmp_path / "tampered.json"
    config_path.write_text(json.dumps(config.model_dump(mode="json")))
    settings = Settings(_env_file=None, environment="test", escape_config=str(config_path))
    problems = run_demo.validate(fake_frontend, settings)
    assert any("does not match the configured expected_circuit_hash" in p.title for p in problems)


def test_missing_frontend_dependencies_are_reported(run_demo, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test")
    problems = run_demo.validate(tmp_path / "frontend", settings)
    assert any("frontend dependencies are missing" in p.title for p in problems)
    assert any("make install-frontend" in p.fix for p in problems)


def test_missing_config_is_reported(run_demo, fake_frontend: Path) -> None:
    settings = Settings(_env_file=None, environment="test", escape_config="does_not_exist")
    problems = run_demo.validate(fake_frontend, settings)
    assert len(problems) == 1 and "escape config" in problems[0].title


def test_cli_help_and_check_flag() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0 and "--check" in result.stdout and "--smoke" in result.stdout
