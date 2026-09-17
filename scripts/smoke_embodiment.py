#!/usr/bin/env python3
"""TECHNICAL EMBODIMENT SMOKE (P7.0) — SIMPLIFIED COMPUTATIONAL BODY.

Structural connectivity is biological data. Neural activity is simulated.
Virtual sensing, motor mapping, body dynamics, and world physics are computational
interpretations.

Closed loop:  SimpleWorld (looming object approaching the origin) → VirtualLoomingSensor →
existing escape_v1 FlyBrain (P4 EscapeExperiment, unchanged parameters) → MotorDecoder →
EscapeMotorAdapter → SimpleBodyAdapter → world advances.  Outcomes are recorded as observed;
nothing is tuned to force an ESCAPE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.behavior import EscapeExperiment, load_escape_circuit, load_escape_config  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embodiment import (  # noqa: E402
    EMBODIMENT_DISCLAIMER,
    EmbodiedAgentLoop,
    EscapeMotorAdapter,
    LoopConfig,
    SimpleBodyAdapter,
    SimpleBodyConfig,
    SimpleWorldAdapter,
    SimpleWorldConfig,
    VirtualLoomingSensor,
)

TITLE = "TECHNICAL EMBODIMENT SMOKE — SIMPLIFIED COMPUTATIONAL BODY"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="escape_v1")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--start-distance", type=float, default=20.0)
    parser.add_argument("--approach-speed", type=float, default=10.0)
    parser.add_argument("--object-size", type=float, default=1.0)
    parser.add_argument("--azimuth-deg", type=float, default=0.0)
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)

    settings = get_settings()
    config = load_escape_config(args.config)
    try:
        circuit = load_escape_circuit(
            config, settings.circuits_data_dir, settings.processed_data_dir, save_if_extracted=False
        )
    except FileNotFoundError as exc:
        print(f"[embodiment] skipped: {exc}")
        return 0
    brain = EscapeExperiment(config, circuit)

    world_config = SimpleWorldConfig(
        start_distance=args.start_distance,
        approach_speed=args.approach_speed,
        object_size=args.object_size,
        azimuth_deg=args.azimuth_deg,
    )
    loop = EmbodiedAgentLoop(
        world=SimpleWorldAdapter(world_config),
        sensor=VirtualLoomingSensor(),
        brain=brain,
        motor=EscapeMotorAdapter(),
        body=SimpleBodyAdapter(SimpleBodyConfig()),
        config=LoopConfig(dt=args.dt, max_steps=max(args.steps, 1)),
    )
    print(f"[embodiment] {TITLE}")
    print(f"[embodiment] {EMBODIMENT_DISCLAIMER}")
    print(
        f"[embodiment] brain={config.config_version} circuit={circuit.circuit_id} "
        f"hash={circuit.provenance.circuit_hash[:12]}… status={config.biological_status} | "
        f"world: looming object r={world_config.object_size} at {world_config.start_distance} "
        f"units, azimuth {world_config.azimuth_deg}°, speed {world_config.approach_speed} units/s "
        f"| loop dt={args.dt}s, {loop.neural_steps} neural steps per loop step"
    )
    loop.reset()
    records = loop.run(args.steps)
    print(
        "[embodiment] step   t    dist   intensity dir     action     command  body(x,y,z)        "
        "grounded"
    )
    for r in records:
        o = r.observation
        p = r.body_state.position
        print(
            f"[embodiment] {r.step_index:4d} {r.simulation_time:5.2f} "
            f"{o.values.get('distance', 0.0):6.2f}   {o.values['intensity']:.3f}   "
            f"{o.metadata['direction']:<7s} {r.brain.action:<10s} {r.command.command:<8s} "
            f"({p.x:6.2f},{p.y:6.2f},{p.z:5.2f})  {r.body_state.grounded}"
        )
    record = loop.record()
    summary = record.summary
    print(f"[embodiment] summary: {summary}")
    if summary["first_escape_step"] is None:
        print(
            "[embodiment] NOTE: the existing escape_v1 model produced NO_ACTION for every "
            "step under this world configuration (reported honestly; nothing was tuned)."
        )
    out_dir = Path(args.out_dir) if args.out_dir else settings.simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "embodiment_smoke.report.json"
    report_path.write_text(
        json.dumps(
            {"title": TITLE, "record": record.model_dump(mode="json")},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"[embodiment] report -> {report_path} (runtime {record.runtime_seconds:.3f}s)")
    problems = []
    if not records:
        problems.append("no steps recorded")
    if any(r.command.command not in ("IDLE", "ESCAPE") for r in records):
        problems.append("unexpected command vocabulary")
    if record.provenance.circuit_hash != (config.expected_circuit_hash or ""):
        problems.append("circuit hash differs from the configured expected hash")
    if problems:
        for problem in problems:
            print(f"[embodiment] FAIL: {problem}", file=sys.stderr)
        return 1
    print("[embodiment] PASS (closed loop executed end-to-end; outcomes recorded as observed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
