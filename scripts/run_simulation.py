#!/usr/bin/env python3
"""Run the simplified LIF-like simulation on a P2 circuit artifact (P3).

    scripts/run_simulation.py --circuit data/circuits/<id>.json --stimulate <neuron_id> \\
        --intensity 2.0 --duration 5 --steps 50 --simulation-id demo

    scripts/run_simulation.py --fixture --stimulate syn_001 --intensity 2.0 --duration 3 --steps 30

Everything this script prints or writes is SIMULATED activity of a computational model;
the circuit's connectivity is the only biological input. The stimulus is GENERIC input
injection (no sensory or behavioural meaning).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.circuits import Circuit, CircuitExtractor, ConnectivityGraph, ExtractorConfig  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.connectome import SyntheticFixtureAdapter  # noqa: E402
from app.connectome.fixture import FIXTURE_SELECTION_RULE  # noqa: E402
from app.simulation import SimulationConfig, SimulationEngine, SimulationError  # noqa: E402


def fixture_circuit() -> Circuit:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    connections = adapter.load_connections(neurons["neuron_id"]).table
    graph = ConnectivityGraph.from_tables(
        neurons, connections, selection_rule=FIXTURE_SELECTION_RULE
    )
    config = ExtractorConfig(
        seed_neuron_ids=["syn_001"], max_hops=2, min_synapses=1, max_neurons=50
    )
    return CircuitExtractor(graph).extract(config, circuit_id="fixture_sim_demo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--circuit", help="path to a circuit artifact JSON")
    source.add_argument("--fixture", action="store_true", help="use the synthetic fixture circuit")
    parser.add_argument("--stimulate", nargs="+", required=True, help="neuron ids to inject into")
    parser.add_argument("--intensity", type=float, default=1.0)
    parser.add_argument("--duration", type=int, default=5, help="stimulus duration in steps")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--simulation-id", default="simulation")
    parser.add_argument("--config-json", help="JSON object overriding SimulationConfig fields")
    parser.add_argument("--out-dir", help="default: data/simulations")
    parser.add_argument("--no-snapshot", action="store_true")
    args = parser.parse_args(argv)

    try:
        overrides = json.loads(args.config_json) if args.config_json else {}
        config = SimulationConfig(**overrides)
        circuit = fixture_circuit() if args.fixture else Circuit.load(Path(args.circuit))
        engine = SimulationEngine(circuit, config)
        engine.stimulate(args.stimulate, args.intensity, args.duration)
        summary = engine.run(args.steps)
    except (SimulationError, ValueError, FileNotFoundError) as exc:
        print(f"[simulate] FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"[simulate] {config.label}")
    print(
        f"[simulate] circuit {circuit.circuit_id} ({engine.num_neurons:,} neurons, "
        f"{engine.num_edges:,} edges) dataset={circuit.dataset} {circuit.dataset_version}"
    )
    print(
        f"[simulate] steps={summary.steps_run} firing_events={summary.firing_events:,} "
        f"neurons_activated={summary.neurons_activated:,} runtime={summary.runtime_seconds:.4f}s "
        f"mean_step={summary.mean_step_seconds * 1e3:.3f} ms"
    )
    print(f"[simulate] per-step fired counts: {summary.per_step_fired_counts}")
    out_dir = Path(args.out_dir) if args.out_dir else get_settings().simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "label": (
            "SIMULATED activity of a simplified LIF-like model; not measured biological activity"
        ),
        "simulation_id": args.simulation_id,
        "circuit_id": circuit.circuit_id,
        "circuit_hash": engine.circuit_hash,
        "simulation_config": config.model_dump(mode="json"),
        "stimuli": [s.model_dump() for s in engine.stimuli],
        "run": summary.model_dump(mode="json"),
        "activity": engine.get_activity(),
    }
    report_path = out_dir / f"{args.simulation_id}.report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[simulate] wrote {report_path}")
    if not args.no_snapshot:
        snapshot_path = engine.snapshot(args.simulation_id).save(
            out_dir / f"{args.simulation_id}.snapshot.json"
        )
        print(f"[simulate] wrote {snapshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
