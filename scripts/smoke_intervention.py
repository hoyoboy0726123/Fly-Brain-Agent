#!/usr/bin/env python3
"""NEURAL INTERVENTION SMOKE (P7.2): CONTROL vs SILENCE_LPLC2 over the live A/B API.

    Computational intervention suppresses simulated firing of selected neurons while
    preserving the biological structural connectivity.

Neural interventions in this lab are computational manipulations of simulated neural
dynamics. They do not reproduce a specific biological silencing, optogenetic, genetic,
pharmacological, or lesion technique. Biological structural connectivity remains unchanged.

Checks (nothing mocked, nothing tuned, no expected behavioural outcome encoded):
    same circuit hash / same world config / same seed across both trials
    target count > 0, resolved from the circuit's cell-type annotations
    LPLC2 simulated fired count in the intervention trial == 0
    structural LPLC2 neurons still exist (node / edge / synapse counts and hash unchanged)
    a comparison result is returned
Whatever the model does (ESCAPE or not) is printed as observed — this is NOT biological
validation. Writes ``data/simulations/intervention_smoke.report.json``. Exit 0 / 1.
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
from app.simulation import INTERVENTION_DISCLAIMER  # noqa: E402

TITLE = "NEURAL INTERVENTION SMOKE — COMPUTATIONAL FIRING SUPPRESSION (CONTROL vs SILENCE_LPLC2)"
STARTUP_TIMEOUT_S = 30.0


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
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (local URL)
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


def trial_lines(name: str, trial: dict, cell_types: tuple[str, ...]) -> list[str]:
    outcome = trial["experiment"]["outcome"]
    totals = trial["simulated_firing_totals"]
    first = outcome["first_escape_step"]
    lines = [f"[intervention] {name}"]
    if trial["role"] == "intervention":
        resolved = trial["resolved_targets"]
        lines.append(f"[intervention]   Target: {' + '.join(resolved['cell_types'])}")
        lines.append(f"[intervention]   Resolved neurons: {resolved['neuron_count']}")
    lines.append(
        f"[intervention]   First escape: {'step ' + str(first) if first is not None else 'NONE'}"
    )
    for cell_type in cell_types:
        label = "GF (DNp01)" if cell_type == "DNp01" else cell_type
        lines.append(f"[intervention]   {label} simulated fired count: {totals.get(cell_type, 0)}")
    lines.append(f"[intervention]   Displacement: {outcome['displacement']:.3f} units")
    lines.append(f"[intervention]   Suppressed threshold crossings: {trial['suppressed_events']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intervention", default="SILENCE_LPLC2")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", str(port), "--log-level", "warning"]  # fmt: skip
    print(f"[intervention] {TITLE}")
    print(f"[intervention] {INTERVENTION_DISCLAIMER}")
    print(f"[intervention] {EMBODIMENT_DISCLAIMER}")
    print(f"[intervention] starting backend on {base}")
    process = subprocess.Popen(command, cwd=BACKEND_DIR)
    problems: list[str] = []
    report: dict = {
        "title": TITLE,
        "intervention_disclaimer": INTERVENTION_DISCLAIMER,
        "disclaimer": EMBODIMENT_DISCLAIMER,
    }
    try:
        wait_for_health(f"{base}/health")
        status, config, _ = http_json(f"{base}/embodiment/intervention/config")
        if status != 200:
            problems.append(f"GET /embodiment/intervention/config -> HTTP {status}: {config}")
            raise RuntimeError("config unavailable")
        selectors = {s["selector"]: s for s in config["selectors"]}
        if args.intervention not in selectors:
            problems.append(f"selector {args.intervention!r} not offered: {sorted(selectors)}")
            raise RuntimeError("unknown selector")
        sig = config["structural_signature"]
        print(
            f"[intervention] circuit {config['circuit_id']} ({config['dataset']} "
            f"{config['dataset_version']}): {sig['node_count']} neurons / {sig['edge_count']} "
            f"edges / {sig['synapse_total']} synapses, hash {sig['circuit_hash'][:12]}…"
        )
        for selector, info in selectors.items():
            print(
                f"[intervention] selector {selector:<18} -> {info['resolved']['neuron_count']:3d} "
                f"neurons {info['resolved']['per_cell_type_counts']}"
            )
        report["config"] = {
            "circuit_id": config["circuit_id"],
            "structural_signature": sig,
            "selectors": {
                s: {
                    "neuron_count": i["resolved"]["neuron_count"],
                    "per_cell_type_counts": i["resolved"]["per_cell_type_counts"],
                }
                for s, i in selectors.items()
            },
        }

        body = {"intervention": args.intervention, "seed": args.seed, "max_steps": args.steps}
        started = time.perf_counter()
        status, result, payload_bytes = http_json(f"{base}/embodiment/intervention/compare", body)
        wall = time.perf_counter() - started
        if status != 200:
            problems.append(
                f"POST /embodiment/intervention/compare {body} -> HTTP {status}: {result}"
            )
            raise RuntimeError("comparison failed")
        control, treated = result["control"], result["intervention"]
        comparison = result["comparison"]
        matched = comparison["matched_conditions"]
        cp = control["experiment"]["provenance"]
        ip = treated["experiment"]["provenance"]
        if cp["circuit_hash"] != ip["circuit_hash"] or cp["circuit_hash"] != sig["circuit_hash"]:
            problems.append("circuit hash differs between trials / config")
        if cp["world_config"] != ip["world_config"]:
            problems.append("world config differs between trials")
        if cp["random_seed"] != ip["random_seed"] or cp["random_seed"] != args.seed:
            problems.append("seed differs between trials")
        if not matched["all_matched"]:
            problems.append(f"matched_conditions not all true: {matched}")
        resolved = treated["resolved_targets"]
        if resolved["neuron_count"] <= 0:
            problems.append("resolved target count is not > 0")
        targets = set(resolved["cell_types"])
        for cell_type in targets:
            fired = treated["simulated_firing_totals"].get(cell_type)
            if fired != 0:
                problems.append(
                    f"{cell_type} simulated fired count in intervention = {fired}, not 0"
                )
        integrity = comparison["structural_integrity"]
        if not integrity["unchanged"]:
            problems.append(f"structural integrity changed: {integrity}")
        for trial in (control, treated):
            if trial["structural_signature"] != sig:
                problems.append(f"{trial['role']} structural signature differs from config")
        # structural neurons of the targeted cell types still exist in the (unchanged) circuit
        groups = {g["cell_type"]: 0 for g in treated["experiment"]["groups"]}
        for g in treated["experiment"]["groups"]:
            groups[g["cell_type"]] += g["neuron_count"]
        for cell_type in targets:
            if groups.get(cell_type, 0) != resolved["per_cell_type_counts"].get(cell_type):
                problems.append(f"structural {cell_type} count changed: {groups.get(cell_type)}")
        cell_types = ("LC4", "LPLC2", "DNp01")
        print("[intervention] " + "-" * 70)
        for line in trial_lines("CONTROL", control, cell_types):
            print(line)
        print("[intervention] " + "-" * 70)
        for line in trial_lines("COMPUTATIONAL INTERVENTION", treated, cell_types):
            print(line)
        print("[intervention] " + "-" * 70)
        print("[intervention] DIFFERENCE (descriptive; current computational model only)")
        for line in comparison["differences"]["summary"]:
            print(f"[intervention]   {line}")
        print(
            f"[intervention] matched conditions: all_matched={matched['all_matched']} | "
            f"structure unchanged={integrity['unchanged']} | sync shared_steps="
            f"{comparison['synchronization']['shared_steps']}"
        )
        print(
            f"[intervention] performance: control {result['runtime']['control_seconds']:.4f}s, "
            f"intervention {result['runtime']['intervention_seconds']:.4f}s, combined "
            f"{result['runtime']['combined_seconds']:.4f}s, HTTP wall {wall:.3f}s, payload "
            f"{payload_bytes / 1024:.1f} KiB"
        )
        print("[intervention] NOT biological validation: the literature motivated the target only.")
        report["comparison"] = {
            "request": body,
            "comparison_id": result["comparison_id"],
            "matched_conditions": matched,
            "structural_integrity": integrity,
            "synchronization": comparison["synchronization"],
            "differences": comparison["differences"],
            "control": {
                "first_escape_step": control["experiment"]["outcome"]["first_escape_step"],
                "simulated_firing_totals": control["simulated_firing_totals"],
                "displacement": control["experiment"]["outcome"]["displacement"],
            },
            "intervention": {
                "resolved_targets": {k: v for k, v in resolved.items() if k != "neuron_ids"},
                "resolved_neuron_ids": resolved["neuron_ids"],
                "first_escape_step": treated["experiment"]["outcome"]["first_escape_step"],
                "simulated_firing_totals": treated["simulated_firing_totals"],
                "suppressed_events": treated["suppressed_events"],
                "displacement": treated["experiment"]["outcome"]["displacement"],
            },
            "performance": {
                **result["runtime"],
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
    report_path = out_dir / "intervention_smoke.report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"[intervention] report written to {report_path}")
    if problems:
        for problem in problems:
            print(f"[intervention] PROBLEM: {problem}")
        print("[intervention] FAILED")
        return 1
    print("[intervention] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
