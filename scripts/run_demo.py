#!/usr/bin/env python3
"""One-command local demo launcher (P6.1): validate, start backend + frontend, print URLs.

    python scripts/run_demo.py            # start both servers, Ctrl+C stops them
    python scripts/run_demo.py --check    # only validate the installation and the artifact
    python scripts/run_demo.py --smoke    # start, verify both URLs answer, stop (CI-friendly)

Validation before anything starts (nothing falls back to synthetic data):
  * backend dependencies importable
  * escape config exists and loads
  * escape circuit artifact exists, is hash-verified and matches the configured hash
  * every configured neuron id is in the circuit (P4 runner checks)
  * frontend dependencies installed (node_modules) and npm available

Works with the interpreter it is run with (``backend/.venv/bin/python`` via ``make demo``,
or any Python that has the backend installed). No developer-specific paths.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
sys.path.insert(0, str(BACKEND_DIR))

REQUIRED_NODE_PACKAGES = ("vite", "react", "react-dom", "d3-force", "d3-zoom", "d3-selection")
STARTUP_TIMEOUT_S = 60.0
IS_WINDOWS = os.name == "nt"


@dataclass
class Problem:
    title: str
    fix: str

    def render(self) -> str:
        return f"  * {self.title}\n      Run: {self.fix}"


def _http_json(url: str, timeout: float = 3.0) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # local URL
        return response.status, json.loads(response.read().decode() or "{}")


def _wait_for(url: str, deadline: float, expect_json: bool = True) -> None:
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if expect_json:
                status, _ = _http_json(url)
            else:
                with urllib.request.urlopen(url, timeout=3) as response:
                    status = response.status
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError) as exc:
            last = exc
        time.sleep(0.3)
    raise TimeoutError(f"{url} did not answer in time ({last!r})")


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


# ----------------------------------------------------------------------------- validation
def validate(frontend_dir: Path = FRONTEND_DIR, settings=None) -> list[Problem]:
    """Return every reason the demo cannot start (empty list = ready)."""
    problems: list[Problem] = []
    try:
        import fastapi  # noqa: F401
        import numpy  # noqa: F401
        import pyarrow  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        problems.append(
            Problem(
                f"backend dependencies are missing ({exc}).",
                "make install-backend   (or: cd backend && python -m venv .venv && "
                '.venv/bin/pip install -e ".[dev]")',
            )
        )
        return problems

    from app.behavior import EscapeExperiment, load_escape_config
    from app.circuits import Circuit
    from app.circuits.errors import ArtifactIntegrityError
    from app.config import get_settings

    settings = settings or get_settings()
    try:
        config = load_escape_config(settings.escape_config)
    except FileNotFoundError:
        problems.append(
            Problem(
                f"escape config {settings.escape_config!r} is missing.",
                "make build-escape-config   (requires the MaleCNS files in data/raw, see DATA.md)",
            )
        )
        return problems
    except Exception as exc:  # noqa: BLE001 - report any config problem verbatim
        problems.append(
            Problem(f"escape config cannot be loaded: {exc}", "make build-escape-config")
        )
        return problems

    circuit_path = settings.circuits_data_dir / f"{config.circuit_id}.json"
    rel = (
        circuit_path.relative_to(PROJECT_ROOT)
        if circuit_path.is_relative_to(PROJECT_ROOT)
        else circuit_path
    )
    if not circuit_path.is_file():
        problems.append(
            Problem(
                f"{config.circuit_id} circuit artifact is missing ({rel}).",
                f"git checkout -- {rel}   (the artifact is committed)  or  "
                "make build-escape-config",
            )
        )
        return problems
    try:
        circuit = Circuit.load(circuit_path, verify=True)
    except ArtifactIntegrityError as exc:
        problems.append(
            Problem(
                f"{config.circuit_id} circuit artifact failed its integrity check: {exc}",
                f"git checkout -- {rel}   or  make build-escape-config",
            )
        )
        return problems
    except Exception as exc:  # noqa: BLE001
        problems.append(Problem(f"{rel} cannot be read: {exc}", f"git checkout -- {rel}"))
        return problems
    circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
    if config.expected_circuit_hash and config.expected_circuit_hash != circuit_hash:
        problems.append(
            Problem(
                f"circuit hash {circuit_hash[:12]}… does not match the configured "
                f"expected_circuit_hash {config.expected_circuit_hash[:12]}….",
                f"git checkout -- {rel} backend/app/behavior/configs/{config.config_version}.json"
                "   or  make build-escape-config",
            )
        )
    else:
        try:
            EscapeExperiment(config, circuit)
        except (ArtifactIntegrityError, ValueError) as exc:
            problems.append(
                Problem(f"escape configuration is inconsistent: {exc}", "make build-escape-config")
            )

    if shutil.which("npm") is None:
        problems.append(
            Problem(
                "npm was not found on PATH.",
                "install Node.js 20.19+ or 22.12+ (https://nodejs.org)",
            )
        )
    missing = [
        name
        for name in REQUIRED_NODE_PACKAGES
        if not (frontend_dir / "node_modules" / name / "package.json").is_file()
    ]
    if missing:
        problems.append(
            Problem(
                f"frontend dependencies are missing ({', '.join(missing)}).",
                "make install-frontend   (or: cd frontend && npm install)",
            )
        )
    return problems


def describe() -> str:
    from app import __version__
    from app.behavior import load_escape_circuit, load_escape_config
    from app.config import get_settings

    settings = get_settings()
    config = load_escape_config(settings.escape_config)
    circuit = load_escape_circuit(config, settings.circuits_data_dir, save_if_extracted=False)
    return (
        f"FlyBrain Agent v{__version__} · {config.config_version} · circuit {circuit.circuit_id} "
        f"({len(circuit.nodes)} neurons / {len(circuit.edges)} edges, hash "
        f"{circuit.provenance.circuit_hash[:12]}… verified) · BIOLOGICAL CIRCUIT STATUS: "
        f"{config.biological_status}"
    )


# ----------------------------------------------------------------------------- processes
def _spawn(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    kwargs: dict = {"cwd": str(cwd), "env": env}
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


def _stop(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
            )
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
        proc.kill()
        proc.wait(timeout=10)
    print(f"[demo] {name} stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--backend-port", type=int, default=int(os.environ.get("FLYBRAIN_BACKEND_PORT", 8000))
    )
    parser.add_argument(
        "--frontend-port", type=int, default=int(os.environ.get("FLYBRAIN_FRONTEND_PORT", 5173))
    )
    parser.add_argument("--check", action="store_true", help="validate only, do not start anything")
    parser.add_argument(
        "--smoke", action="store_true", help="start, verify both servers answer, stop"
    )
    parser.add_argument("--open", action="store_true", help="open the demo in the default browser")
    args = parser.parse_args(argv)

    problems = validate()
    if problems:
        print("FlyBrain Agent cannot start:")
        for problem in problems:
            print(problem.render())
        return 1
    print(f"[demo] {describe()}")
    if args.check:
        print("[demo] check PASS — ready to start (make demo)")
        return 0

    for name, port in (("backend", args.backend_port), ("frontend", args.frontend_port)):
        if not _port_free(port):
            print(
                f"FlyBrain Agent cannot start:\n  * port {port} for the {name} is already in use."
            )
            print(f"      Run: python scripts/run_demo.py --{name}-port <free port>")
            return 1

    backend_url = f"http://127.0.0.1:{args.backend_port}"
    frontend_url = f"http://127.0.0.1:{args.frontend_port}"
    env = dict(os.environ)
    env.update(
        {"FLYBRAIN_BACKEND_URL": backend_url, "FLYBRAIN_FRONTEND_PORT": str(args.frontend_port)}
    )
    npm = shutil.which("npm") or "npm"

    print(f"[demo] starting backend on {backend_url} …")
    backend_command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1"]
    backend_command += ["--port", str(args.backend_port), "--log-level", "warning"]
    backend = _spawn(backend_command, BACKEND_DIR, env)
    frontend: subprocess.Popen | None = None
    try:
        _wait_for(f"{backend_url}/health", time.monotonic() + STARTUP_TIMEOUT_S)
        print(f"[demo] starting frontend on {frontend_url} …")
        frontend = _spawn([npm, "run", "dev", "--silent"], FRONTEND_DIR, env)
        _wait_for(frontend_url, time.monotonic() + STARTUP_TIMEOUT_S, expect_json=False)
        status, config = _http_json(f"{frontend_url}/api/escape/config", timeout=10)
        if status != 200 or config.get("circuit_id") is None:
            raise RuntimeError(f"frontend proxy did not reach the backend (HTTP {status})")
        print()
        print("  FlyBrain Agent is running")
        print(f"  Demo:       {frontend_url}/")
        print(f"  Inspector:  {frontend_url}/#inspector")
        print(f"  API docs:   {backend_url}/docs")
        print(f"  Circuit:    {config['circuit_id']} · hash {config['circuit_hash'][:12]}… · "
              f"BIOLOGICAL CIRCUIT STATUS: {config['biological_status']}")  # fmt: skip
        print("  Press Ctrl+C to stop.")
        print()
        if args.smoke:
            print("[demo] startup smoke PASS (backend + frontend + proxy answered)")
            return 0
        if args.open:
            webbrowser.open(frontend_url)
        while True:
            time.sleep(0.5)
            for name, proc in (("backend", backend), ("frontend", frontend)):
                if proc is not None and proc.poll() is not None:
                    print(f"[demo] {name} exited with code {proc.returncode}; stopping")
                    return 1
    except KeyboardInterrupt:
        print("\n[demo] stopping …")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[demo] FAIL: {exc}")
        return 1
    finally:
        if frontend is not None:
            _stop(frontend, "frontend")
        _stop(backend, "backend")


if __name__ == "__main__":
    sys.exit(main())
