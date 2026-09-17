#!/usr/bin/env python3
"""VIRTUAL THREAT LAB SMOKE (P7.1): boot the API and replay one closed-loop experiment.

Structural connectivity is biological data. Neural activity is simulated.
Virtual sensing, motor mapping, body dynamics, and world physics are computational
interpretations.

Checks (over live HTTP, nothing mocked, nothing tuned):
    GET  /embodiment/config   -> experiment, labels, circuit, timing, boundaries, disclaimer
    POST /embodiment/run      -> timeline non-empty and ordered, world/sensor values change,
                                 brain/motor/body/provenance present on every step,
                                 if an ESCAPE is decoded the body position changes afterwards.
The outcome is recorded as observed. Writes ``data/simulations/threat_lab_smoke.report.json``.
Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import argparse
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

from app.config import get_settings  # noqa: E402
from app.embodiment import EMBODIMENT_DISCLAIMER  # noqa: E402

TITLE = "VIRTUAL THREAT LAB SMOKE — REPLAY OF A BACKEND-GENERATED CLOSED LOOP"
STARTUP_TIMEOUT_S = 30.0
EXPECTED_LABELS = {
    "world_physics": "COMPUTATIONAL",
    "virtual_sensing": "COMPUTATIONAL SENSOR INPUT",
    "neural_activity": "SIMULATED",
    "structural_connectivity": "BIOLOGICAL DATA",
    "body": "SIMPLIFIED COMPUTATIONAL BODY",
}
STAGE_KEYS = ("world", "body", "sensor", "brain", "motor")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(url: str, body: dict | None = None) -> tuple[int, dict, int]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"content-type": "application/json", "accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (local URL)
            raw = response.read()
            return response.status, json.loads(raw.decode()), len(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, json.loads(raw.decode() or "{}"), len(raw)


def wait_for_health(url: str) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _, _ = http_json(url)
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = exc
        time.sleep(0.25)
    raise TimeoutError(f"backend not healthy at {url}: {last!r}")


def check_timeline(timeline: list[dict], problems: list[str]) -> None:
    if not timeline:
        problems.append("timeline is empty")
        return
    indices = [s["step_index"] for s in timeline]
    if indices != list(range(len(timeline))):
        problems.append(f"timeline step_index not ordered: {indices[:8]}…")
    times = [s["simulation_time"] for s in timeline]
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        problems.append("simulation_time is not strictly increasing")
    for step in timeline:
        missing = [k for k in STAGE_KEYS if k not in step]
        if missing:
            problems.append(f"step {step.get('step_index')} lacks {missing}")
            break
        brain = step["brain"]
        if brain["label"] != "SIMULATED NEURAL ACTIVITY" or "group_fired_counts" not in brain:
            problems.append(
                f"step {step['step_index']}: brain panel data is not labelled SIMULATED"
            )
            break
        if brain["action"] not in ("NO_ACTION", "ESCAPE"):
            problems.append(f"step {step['step_index']}: unexpected action {brain['action']!r}")
        if step["motor"]["command"] not in ("IDLE", "ESCAPE"):
            problems.append(f"step {step['step_index']}: unexpected command {step['motor']}")
    distances = [s["sensor"]["distance"] for s in timeline]
    xs = [s["world"]["objects"][0]["position"]["x"] for s in timeline if s["world"]["objects"]]
    if len(set(xs)) < 2:
        problems.append("world object position never changes")
    if len({round(d, 6) for d in distances if d is not None}) < 2:
        problems.append("sensor distance never changes")
    intensities = [s["sensor"]["intensity"] for s in timeline]
    if len({round(i, 6) for i in intensities}) < 2:
        problems.append("looming input never changes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--start-distance", type=float, default=20.0)
    parser.add_argument("--approach-speed", type=float, default=10.0)
    parser.add_argument("--azimuth-deg", type=float, default=0.0)
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", str(port), "--log-level", "warning"]  # fmt: skip
    print(f"[threat-lab] {TITLE}")
    print(f"[threat-lab] {EMBODIMENT_DISCLAIMER}")
    print(f"[threat-lab] starting backend on {base}")
    process = subprocess.Popen(command, cwd=BACKEND_DIR)
    problems: list[str] = []
    report: dict = {"title": TITLE, "disclaimer": EMBODIMENT_DISCLAIMER}
    try:
        wait_for_health(f"{base}/health")
        status, config, _ = http_json(f"{base}/embodiment/config")
        if status != 200:
            problems.append(f"GET /embodiment/config -> HTTP {status}: {config}")
            raise RuntimeError("config unavailable")
        circuit = config["circuit"]
        print(
            f"[threat-lab] config: {config['experiment_name']} "
            f"brain={config['escape_config_version']} circuit={circuit['circuit_id']} "
            f"hash={circuit['circuit_hash'][:12]}… "
            f"({circuit['neurons']} neurons / {circuit['edges']} edges) "
            f"BIOLOGICAL CIRCUIT STATUS: {circuit['biological_status']} | loop dt="
            f"{config['timing']['loop_dt']} s, {config['timing']['neural_steps_per_loop_step']} "
            f"neural steps per loop step"
        )
        for key, expected in EXPECTED_LABELS.items():
            if config["labels"].get(key) != expected:
                problems.append(f"label {key!r} is {config['labels'].get(key)!r}, not {expected!r}")
        if config["disclaimer"] != EMBODIMENT_DISCLAIMER:
            problems.append("config disclaimer differs from EMBODIMENT_DISCLAIMER")
        if not config.get("scientific_boundaries"):
            problems.append("config has no scientific boundaries")
        report["config"] = {
            "experiment_name": config["experiment_name"],
            "circuit": circuit,
            "timing": config["timing"],
            "labels": config["labels"],
            "max_loop_steps": config["max_loop_steps"],
        }

        body = {
            "seed": args.seed,
            "max_steps": args.steps,
            "world": {
                "start_distance": args.start_distance,
                "approach_speed": args.approach_speed,
                "azimuth_deg": args.azimuth_deg,
            },
        }
        started = time.perf_counter()
        status, result, payload_bytes = http_json(f"{base}/embodiment/run", body)
        wall = time.perf_counter() - started
        if status != 200:
            problems.append(f"POST /embodiment/run {body} -> HTTP {status}: {result}")
            raise RuntimeError("run failed")
        timeline = result["timeline"]
        check_timeline(timeline, problems)
        if result["disclaimer"] != EMBODIMENT_DISCLAIMER:
            problems.append("run disclaimer differs from EMBODIMENT_DISCLAIMER")
        prov = result.get("provenance") or {}
        for key in ("circuit_hash", "dataset", "escape_config_version", "world_adapter",
                    "sensor_adapter", "motor_adapter", "body_adapter", "loop_config"):  # fmt: skip
            if key not in prov:
                problems.append(f"provenance lacks {key!r}")
        if prov.get("circuit_hash") != circuit["circuit_hash"]:
            problems.append("provenance circuit hash differs from config")
        outcome = result["outcome"]
        first = outcome["first_escape_step"]
        print(
            "[threat-lab] step   t    dist   intensity dir     action     command  "
            "body(x,y,z)         grounded  DNp01 peak"
        )
        for s in timeline:
            p = s["body"]["position"]
            peak = s["brain"]["group_peak_fired"]
            print(
                f"[threat-lab] {s['step_index']:4d} {s['simulation_time']:5.2f} "
                f"{(s['sensor']['distance'] or 0.0):6.2f}   {s['sensor']['intensity']:.3f}   "
                f"{s['sensor']['direction']:<7s} {s['brain']['action']:<10s} "
                f"{s['motor']['command']:<8s} ({p['x']:6.2f},{p['y']:6.2f},{p['z']:5.2f})  "
                f"{str(s['body']['grounded']):<8s} L={peak.get('DNp01_L', 0)} "
                f"R={peak.get('DNp01_R', 0)}"
            )
        if first is not None:
            if first + 1 >= len(timeline):
                print("[threat-lab] NOTE: ESCAPE decoded on the last step; no later body state")
            else:
                before = timeline[first]["body"]["position"]
                after = timeline[first + 1]["body"]["position"]
                if before == after:
                    problems.append(
                        f"ESCAPE at step {first} but the body position did not change afterwards"
                    )
                if not any(sum(v) for v in timeline[first]["brain"]["group_fired_counts"].values()):
                    problems.append(f"ESCAPE at step {first} without any simulated group activity")
            events = [(e["kind"], e["step_index"]) for e in outcome["events"]]
            if ("first_escape", first) not in events:
                problems.append(f"events lack ('first_escape', {first}): {events}")
        else:
            print(
                "[threat-lab] NOTE: the existing escape_v1 model produced NO_ACTION for every "
                "step under this world configuration (reported honestly; nothing was tuned)."
            )
        print(
            f"[threat-lab] outcome: first_escape_step={first} "
            f"escape_steps={outcome['escape_steps']} displacement={outcome['displacement']:.3f} "
            f"final_grounded={outcome['final_grounded']}"
            f" | backend runtime={result['runtime_seconds']:.4f}s wall={wall:.3f}s "
            f"payload={payload_bytes / 1024:.1f} KiB for {len(timeline)} steps"
        )
        report["run"] = {
            "request": body,
            "experiment_id": result["experiment_id"],
            "steps": len(timeline),
            "outcome": outcome,
            "provenance": prov,
            "performance": {
                "backend_runtime_seconds": result["runtime_seconds"],
                "http_wall_seconds": round(wall, 4),
                "payload_bytes": payload_bytes,
            },
        }
    except Exception as exc:  # noqa: BLE001 — report every failure as a smoke problem
        problems.append(f"{type(exc).__name__}: {exc}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    report["problems"] = problems
    out_dir = Path(args.out_dir) if args.out_dir else get_settings().simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "threat_lab_smoke.report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"[threat-lab] report written to {report_path}")
    if problems:
        for problem in problems:
            print(f"[threat-lab] PROBLEM: {problem}")
        print("[threat-lab] FAILED")
        return 1
    print("[threat-lab] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
