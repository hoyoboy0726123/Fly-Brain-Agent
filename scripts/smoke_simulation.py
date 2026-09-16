#!/usr/bin/env python3
"""P3 smoke test.

1. Fixture propagation demo (synthetic circuit): stimulate the seed → seed fires → hop-1
   neurons fire → hop-2 neurons fire → activity stops once stimulation ends.
2. If the P2 technical MaleCNS circuit is available locally:
   TECHNICAL CONNECTOME-GROUNDED SIMULATION — NOT A BIOLOGICAL ACTIVITY CLAIM.
   Loads the real extracted circuit, injects a GENERIC stimulus into its technical seed
   neuron, runs a short simulation and records size/activity/runtime/memory figures.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.circuits import Circuit, CircuitExtractor, ConnectivityGraph, ExtractorConfig  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.connectome import SyntheticFixtureAdapter  # noqa: E402
from app.connectome.fixture import FIXTURE_SELECTION_RULE  # noqa: E402
from app.simulation import SimulationConfig, SimulationEngine, peak_rss_bytes  # noqa: E402

TECHNICAL_LABEL = "TECHNICAL CONNECTOME-GROUNDED SIMULATION — NOT A BIOLOGICAL ACTIVITY CLAIM"
TECHNICAL_CIRCUIT = "smoke_technical_downstream_min10_hops2"


def fixture_demo() -> bool:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    connections = adapter.load_connections(neurons["neuron_id"]).table
    graph = ConnectivityGraph.from_tables(
        neurons, connections, selection_rule=FIXTURE_SELECTION_RULE
    )
    circuit = CircuitExtractor(graph).extract(
        ExtractorConfig(seed_neuron_ids=["syn_001"], max_hops=2, min_synapses=1, max_neurons=50),
        circuit_id="fixture_smoke_downstream",
    )
    hop = {node.neuron_id: node.minimum_hop_from_seed for node in circuit.nodes}
    engine = SimulationEngine(circuit, SimulationConfig())
    engine.stimulate(["syn_001"], intensity=2.0, duration_steps=3)
    summary = engine.run(30)
    first = summary.first_fire_step
    fired_hops = {h: sorted(n for n, s in first.items() if hop[n] == h) for h in (0, 1, 2)}
    ordered = all(first[a] < first[b] for a in fired_hops[0] for b in fired_hops[1]) and all(
        first[a] < first[b] for a in fired_hops[1] for b in fired_hops[2]
    )
    tail = summary.per_step_fired_counts[-10:]
    state = engine.get_state()
    settled = all(
        abs(n.membrane_potential - engine.config.resting_potential) < 1e-3 for n in state.neurons
    )
    ok = bool(
        fired_hops[0] and fired_hops[1] and fired_hops[2] and ordered and not any(tail) and settled
    )
    print(
        f"[smoke-sim] fixture: firing events={summary.firing_events} "
        f"activated={summary.neurons_activated}/{engine.num_neurons} "
        f"first-fire by hop={fired_hops} per-step={summary.per_step_fired_counts} "
        f"settled={settled} -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def load_or_extract_technical_circuit(circuits_dir: Path, processed_dir: Path) -> Circuit | None:
    path = circuits_dir / f"{TECHNICAL_CIRCUIT}.json"
    if path.is_file():
        return Circuit.load(path)
    perf = circuits_dir / "smoke_technical_extraction.perf.json"
    if not (processed_dir / "neurons.parquet").is_file() or not perf.is_file():
        return None
    runs = [
        r for r in json.loads(perf.read_text())["runs"] if r.get("circuit_id") == TECHNICAL_CIRCUIT
    ]
    if not runs:
        return None
    graph = ConnectivityGraph.load(processed_dir)
    circuit = CircuitExtractor(graph).extract(
        ExtractorConfig(**runs[0]["config"]),
        circuit_id=TECHNICAL_CIRCUIT,
        notes=runs[0].get("label", ""),
    )
    circuit.save(circuits_dir)
    return circuit


def technical_smoke(circuits_dir: Path, processed_dir: Path, out_dir: Path) -> bool | None:
    circuit = load_or_extract_technical_circuit(circuits_dir, processed_dir)
    if circuit is None:
        print("[smoke-sim] technical: no MaleCNS circuit or normalized data available; skipped")
        return None
    print(f"[smoke-sim] {TECHNICAL_LABEL}")
    runs: dict[str, dict] = {}
    # (a) default COMPUTATIONAL parameters; (b) a damped variant (smaller weight_scale) to show
    # that whether activity persists or decays is a property of the model parameters.
    variants = {
        "default": SimulationConfig(),
        "damped_weight_scale_0.05": SimulationConfig(weight_scale=0.05),
    }
    ok = True
    for name, config in variants.items():
        t0 = time.perf_counter()
        engine = SimulationEngine(circuit, config)
        build_s = time.perf_counter() - t0
        engine.stimulate(circuit.seed_neurons, intensity=2.0, duration_steps=5)
        summary = engine.run(50)
        bench = SimulationEngine(circuit, config)
        bench.stimulate(circuit.seed_neurons, intensity=2.0, duration_steps=5)
        bench_summary = bench.run(1000)
        tail_quiet = not any(summary.per_step_fired_counts[-10:])
        state = engine.get_state()
        settled = all(
            abs(n.membrane_potential - config.resting_potential) < 1e-6 for n in state.neurons
        )
        snapshot_path = engine.snapshot(f"smoke_technical_simulation_{name}").save(
            out_dir / f"smoke_technical_simulation_{name}.snapshot.json"
        )
        runs[name] = {
            "simulation_config": config.model_dump(mode="json"),
            "stimulus": [st.model_dump() for st in engine.stimuli],
            "simulation_steps": summary.steps_run,
            "neurons_activated": summary.neurons_activated,
            "firing_events": summary.firing_events,
            "per_step_fired_counts": summary.per_step_fired_counts,
            "activity_stopped_in_last_10_steps": tail_quiet,
            "settled_to_rest": settled,
            "engine_build_seconds": round(build_s, 6),
            "runtime_seconds": round(summary.runtime_seconds, 6),
            "mean_step_seconds": round(summary.mean_step_seconds, 8),
            "benchmark_1000_steps": {
                "runtime_seconds": round(bench_summary.runtime_seconds, 6),
                "mean_step_seconds": round(bench_summary.mean_step_seconds, 8),
                "firing_events": bench_summary.firing_events,
            },
            "snapshot": (
                str(snapshot_path.relative_to(PROJECT_ROOT))
                if snapshot_path.is_relative_to(PROJECT_ROOT)
                else str(snapshot_path)
            ),
        }
        if name == "default":
            ok = summary.firing_events > 0 and summary.neurons_activated > len(circuit.seed_neurons)
        print(
            f"[smoke-sim] technical[{name}]: circuit {engine.num_neurons:,} neurons / "
            f"{engine.num_edges:,} edges; steps={summary.steps_run} "
            f"activated={summary.neurons_activated:,} firing_events={summary.firing_events:,} "
            f"stopped={tail_quiet} settled={settled} runtime={summary.runtime_seconds:.4f}s "
            f"mean_step={summary.mean_step_seconds * 1e3:.3f} ms "
            f"(1000-step bench {bench_summary.mean_step_seconds * 1e3:.3f} ms/step)"
        )
    # parameter-sensitivity sweep (computational only): how weight_scale changes the outcome
    sweep: list[dict] = []
    for scale in (0.1, 0.15, 0.2, 0.3, 0.5):
        engine = SimulationEngine(circuit, SimulationConfig(weight_scale=scale))
        engine.stimulate(circuit.seed_neurons, intensity=2.0, duration_steps=5)
        summary = engine.run(50)
        sweep.append(
            {
                "weight_scale": scale,
                "neurons_activated": summary.neurons_activated,
                "firing_events": summary.firing_events,
                "activity_stopped_in_last_10_steps": not any(summary.per_step_fired_counts[-10:]),
                "per_step_fired_counts_first_15": summary.per_step_fired_counts[:15],
            }
        )
        stopped = sweep[-1]["activity_stopped_in_last_10_steps"]
        print(
            f"[smoke-sim] sweep weight_scale={scale}: activated={summary.neurons_activated:,} "
            f"events={summary.firing_events:,} stopped={stopped} "
            f"first steps={summary.per_step_fired_counts[:12]}"
        )
    report = {
        "label": TECHNICAL_LABEL,
        "weight_scale_sweep": sweep,
        "note": (
            "Seeds were chosen mechanically in P2; the stimulus is generic input injection. "
            "Whether activity persists or decays after the stimulus depends on the computational "
            "parameters (unsigned excitatory-only weights, no inhibition); no biological meaning."
        ),
        "circuit_id": circuit.circuit_id,
        "circuit_hash": engine.circuit_hash,
        "circuit_neurons": engine.num_neurons,
        "circuit_edges": engine.num_edges,
        "seed_neurons": circuit.seed_neurons,
        "peak_rss_bytes": peak_rss_bytes(),
        "runs": runs,
    }
    peak_mb = (report["peak_rss_bytes"] or 0) / 1e6
    print(f"[smoke-sim] technical peak_rss={peak_mb:.0f} MB -> {'PASS' if ok else 'FAIL'}")
    report_path = out_dir / "smoke_technical_simulation.report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[smoke-sim] report -> {report_path}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--fixture-only", action="store_true")
    parser.add_argument("--circuits-dir")
    parser.add_argument("--processed-dir")
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)
    settings = get_settings()
    out_dir = Path(args.out_dir) if args.out_dir else settings.simulations_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = fixture_demo()
    if not args.fixture_only:
        circuits_dir = Path(args.circuits_dir) if args.circuits_dir else settings.circuits_data_dir
        processed_dir = (
            Path(args.processed_dir) if args.processed_dir else settings.processed_data_dir
        )
        technical = technical_smoke(circuits_dir, processed_dir, out_dir)
        ok = ok and (technical is not False)
    print(f"[smoke-sim] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
