#!/usr/bin/env python3
"""TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO (P4, Phase G).

STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED.
STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.

Runs the escape_v1 pipeline (LoomingStimulus → StimulusMapper → SimulationEngine →
MotorDecoder) for left/center/right × several intensities and records the outcome
honestly, whether or not an ESCAPE is decoded. Nothing is tuned toward an outcome: the
P3 simulation defaults are used unless the config records overrides.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.behavior import (  # noqa: E402
    DISCLAIMER,
    EscapeExperiment,
    load_escape_circuit,
    load_escape_config,
)
from app.config import get_settings  # noqa: E402
from app.sensors import LoomingStimulus  # noqa: E402

TITLE = "TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="escape_v1")
    parser.add_argument("--circuits-dir")
    parser.add_argument("--processed-dir")
    parser.add_argument("--out-dir")
    parser.add_argument("--intensities", nargs="*", type=float, default=[0.2, 0.5, 1.0])
    parser.add_argument("--steps", type=int)
    args = parser.parse_args(argv)
    settings = get_settings()
    circuits_dir = Path(args.circuits_dir) if args.circuits_dir else settings.circuits_data_dir
    processed_dir = Path(args.processed_dir) if args.processed_dir else settings.processed_data_dir
    out_dir = Path(args.out_dir) if args.out_dir else settings.simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    config = load_escape_config(args.config)
    try:
        circuit = load_escape_circuit(config, circuits_dir, processed_dir)
    except FileNotFoundError as exc:
        print(f"[escape-demo] skipped: {exc}")
        return 0

    print(f"[escape-demo] {TITLE}")
    print(f"[escape-demo] {DISCLAIMER}")
    print(
        f"[escape-demo] config={config.config_version} status={config.biological_status} "
        f"circuit={circuit.circuit_id} ({len(circuit.nodes)} neurons / {len(circuit.edges)} edges) "
        f"hash={circuit.provenance.circuit_hash[:12]}… sensory={len(config.all_sensory_ids())} "
        f"({config.sensory_cell_types}) output={config.all_output_ids()} "
        f"({config.output_cell_types})"
    )
    experiment = EscapeExperiment(config, circuit)
    print(
        "[escape-demo] simulation config: "
        f"{experiment.simulation_config.model_dump(exclude={'label'})}"
    )

    runs = []
    started = time.perf_counter()
    for direction in ("left", "center", "right"):
        for intensity in args.intensities:
            stimulus = LoomingStimulus(direction=direction, intensity=intensity)
            result = experiment.run(stimulus, steps=args.steps)
            t1 = next(e for e in result.timeline if e.tag == "t1_sensory_activation")
            t3 = next(e for e in result.timeline if e.tag == "t3_output_activation")
            outputs = {o.neuron_id + f"({o.side})": o.spike_count for o in result.output_activity}
            print(
                f"[escape-demo] direction={direction:<6} intensity={intensity:<4} -> "
                f"{result.decision.action.value:<9} sensory fired step={t1.step} "
                f"({t1.count} neurons) | output fired step={t3.step} spikes={outputs} | "
                f"events={result.firing_events} activated={result.neurons_activated} "
                f"per-step={result.per_step_fired_counts[:10]}… "
                f"runtime={result.runtime_seconds:.4f}s"
            )
            # per-neuron state history (P6 inspector replay) is ~65 KB per run; keep the
            # committed report small — the API serves it on demand
            runs.append(result.model_dump(mode="json", exclude={"neuron_activity"}))
    total = time.perf_counter() - started

    decoded = {
        (r["stimulus"]["direction"], r["stimulus"]["intensity"]): r["decision"]["action"]
        for r in runs
    }
    report = {
        "title": TITLE,
        "disclaimer": DISCLAIMER,
        "config_version": config.config_version,
        "biological_status": config.biological_status,
        "research_document": config.research_document,
        "circuit": {
            "circuit_id": circuit.circuit_id,
            "circuit_hash": circuit.provenance.circuit_hash,
            "neurons": len(circuit.nodes),
            "edges": len(circuit.edges),
            "dataset": circuit.dataset,
            "dataset_version": circuit.dataset_version,
        },
        "sensory_neurons": {side: len(ids) for side, ids in config.sensory_groups.items()},
        "output_neurons": config.output_groups,
        "simulation_config": experiment.simulation_config.model_dump(mode="json"),
        "decisions": [
            {"direction": k[0], "intensity": k[1], "action": v} for k, v in decoded.items()
        ],
        "runs": runs,
        "total_runtime_seconds": round(total, 4),
    }
    report_path = out_dir / "escape_v1_demo.report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"[escape-demo] decisions: {[(k[0], k[1], v) for k, v in decoded.items()]}")
    print(f"[escape-demo] report -> {report_path} (total runtime {total:.3f}s)")
    print("[escape-demo] PASS (pipeline executed end-to-end; outcomes recorded as observed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
