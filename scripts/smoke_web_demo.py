#!/usr/bin/env python3
"""WEB DEMO SMOKE (P5): boot the API, run the three demo scenarios over REST and WebSocket.

STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED.
STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.

Scenarios (the outcomes observed and recorded in the P4 report, used as regression checks):
    CENTER 0.2 -> NO_ACTION      CENTER 0.5 -> ESCAPE      LEFT 1.0 -> ESCAPE (GF Left)
Writes ``data/simulations/web_demo_smoke.report.json``. Exit code 0 on success, 1 on failure.
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
sys.path.insert(0, str(BACKEND_DIR))

from app.behavior import DISCLAIMER  # noqa: E402
from app.config import get_settings  # noqa: E402

TITLE = "WEB DEMO SMOKE — SIMULATED ACTIVITY, DECODED ACTION"
SCENARIOS = (
    ("center", 0.2, "NO_ACTION", "None"),
    ("center", 0.5, "ESCAPE", "Both"),
    ("left", 1.0, "ESCAPE", "Left"),
)
STARTUP_TIMEOUT_S = 30.0


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"content-type": "application/json", "accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (local URL)
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def wait_for_health(url: str) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _ = http_json(url)
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = exc
        time.sleep(0.25)
    raise TimeoutError(f"backend not healthy at {url}: {last!r}")


def run_socket(ws_url: str, direction: str, intensity: float) -> list[dict]:
    from websockets.sync.client import connect

    events: list[dict] = []
    with connect(ws_url, open_timeout=10) as ws:
        ws.send(json.dumps({"stimulus": "looming", "direction": direction, "intensity": intensity}))
        while True:
            event = json.loads(ws.recv(timeout=10))
            events.append(event)
            if event["event"] in ("experiment_finished", "error"):
                return events


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", str(port), "--log-level", "warning"]  # fmt: skip
    print(f"[web-demo] {TITLE}")
    print(f"[web-demo] {DISCLAIMER}")
    print(f"[web-demo] starting backend on {base}")
    process = subprocess.Popen(command, cwd=BACKEND_DIR)
    problems: list[str] = []
    report: dict = {"title": TITLE, "disclaimer": DISCLAIMER, "scenarios": []}
    try:
        wait_for_health(f"{base}/health")
        status, config = http_json(f"{base}/escape/config")
        if status != 200:
            problems.append(f"GET /escape/config -> HTTP {status}: {config}")
            raise RuntimeError("config unavailable")
        print(
            f"[web-demo] config: {config['config_version']} circuit={config['circuit_id']} "
            f"hash={config['circuit_hash'][:12]}… verified={config['circuit_verified']} "
            f"({config['circuit_neurons']} neurons / {config['circuit_edges']} edges) "
            f"BIOLOGICAL CIRCUIT STATUS: {config['biological_status']}"
        )
        report["config"] = {
            k: config[k]
            for k in (
                "config_version", "circuit_id", "circuit_hash", "circuit_verified",
                "biological_status", "circuit_neurons", "circuit_edges", "dataset",
                "dataset_version", "simulation_steps", "stimulus_duration_steps",
            )
        }  # fmt: skip
        if config["biological_status"] != "PARTIALLY SUPPORTED":
            problems.append(f"unexpected biological_status {config['biological_status']!r}")

        ws_url = f"ws://127.0.0.1:{port}/ws/escape"
        for direction, intensity, expected_action, expected_gf in SCENARIOS:
            body = {"stimulus": "looming", "direction": direction, "intensity": intensity}
            status, result = http_json(f"{base}/escape/run", body)
            if status != 200:
                problems.append(f"POST /escape/run {body} -> HTTP {status}: {result}")
                continue
            events = run_socket(ws_url, direction, intensity)
            kinds = [e["event"] for e in events]
            ws_result = events[-1].get("result", {})
            t1 = result["sensory_activity"]["first_fire_step"]
            t3 = result["decision"]["first_output_fire_step"]
            line = (
                f"[web-demo] {direction.upper():<6} {intensity:<4} -> {result['action']:<9} "
                f"GF activity: {result['gf_activity']:<5} sensory step={t1} GF step={t3} "
                f"ws events={len(kinds)} ({kinds.count('neural_activity')} neural_activity) "
                f"runtime={result['runtime_seconds']:.4f}s"
            )
            print(line)
            scenario = {
                "direction": direction,
                "intensity": intensity,
                "expected_action": expected_action,
                "action": result["action"],
                "gf_activity": result["gf_activity"],
                "first_sensory_step": t1,
                "first_output_step": t3,
                "experiment_id": result["experiment_id"],
                "circuit_hash": result["circuit_hash"],
                "websocket_events": kinds,
                "websocket_action": ws_result.get("action"),
            }
            report["scenarios"].append(scenario)
            if result["action"] != expected_action:
                problems.append(f"{direction} {intensity}: got {result['action']}, "
                                f"expected {expected_action}")  # fmt: skip
            if result["gf_activity"] != expected_gf:
                problems.append(f"{direction} {intensity}: GF activity {result['gf_activity']}")
            if result["disclaimer"] != DISCLAIMER:
                problems.append(f"{direction} {intensity}: disclaimer differs")
            if result["circuit_hash"] != config["circuit_hash"]:
                problems.append(f"{direction} {intensity}: circuit hash differs from config")
            if ws_result.get("action") != result["action"]:
                problems.append(f"{direction} {intensity}: WebSocket action differs from REST")
            tail = ["action_decoded", "experiment_finished"]
            if kinds[0] != "stimulus_started" or kinds[-2:] != tail:
                problems.append(f"{direction} {intensity}: unexpected WS event order {kinds}")
            if result["action"] == "ESCAPE" and "output_activation" not in kinds:
                problems.append(f"{direction} {intensity}: ESCAPE without output_activation event")

        status, _ = http_json(f"{base}/escape/run", {"direction": "center", "intensity": 1.5})
        print(f"[web-demo] invalid intensity 1.5 -> HTTP {status}")
        report["invalid_intensity_status"] = status
        if status != 422:
            problems.append(f"invalid intensity accepted with HTTP {status}")
    except Exception as exc:  # noqa: BLE001 - report any failure
        problems.append(repr(exc))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    out_dir = get_settings().simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report["problems"] = problems
    report_path = out_dir / "web_demo_smoke.report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"[web-demo] report -> {report_path}")
    if problems:
        for problem in problems:
            print(f"[web-demo] FAIL: {problem}", file=sys.stderr)
        return 1
    print("[web-demo] PASS (REST + WebSocket demo scenarios behave as recorded in P4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
