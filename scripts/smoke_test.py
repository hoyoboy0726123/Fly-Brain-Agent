#!/usr/bin/env python3
"""Backend smoke test for P0: start the API, hit GET /health, verify the payload.

Uses only the standard library so it can run with the backend virtualenv's Python
(``backend/.venv/bin/python scripts/smoke_test.py``) or any interpreter that has the
backend dependencies installed. Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
STARTUP_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.25


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(url: str, deadline: float) -> dict[str, object]:
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 (local URL)
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
                last_error = RuntimeError(f"HTTP {response.status}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"backend did not become healthy at {url}: {last_error!r}")


def main() -> int:
    port = free_port()
    url = f"http://127.0.0.1:{port}/health"
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    print(f"[smoke] starting backend: {' '.join(command)} (cwd={BACKEND_DIR})")
    process = subprocess.Popen(command, cwd=BACKEND_DIR)
    try:
        payload = wait_for_health(url, time.monotonic() + STARTUP_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 - report any startup failure
        print(f"[smoke] FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    print(f"[smoke] GET {url} -> {json.dumps(payload, sort_keys=True)}")
    problems: list[str] = []
    if payload.get("status") != "ok":
        problems.append(f"status is {payload.get('status')!r}, expected 'ok'")
    for key in ("service", "version", "environment", "phase"):
        if not payload.get(key):
            problems.append(f"missing or empty field {key!r}")
    if problems:
        for problem in problems:
            print(f"[smoke] FAIL: {problem}", file=sys.stderr)
        return 1

    print("[smoke] PASS: backend /health is healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
