#!/usr/bin/env python3
"""P2 smoke test: fixture extraction with a known expected result, then (if the normalized
MaleCNS tables exist locally) a TECHNICAL EXTRACTION SMOKE TEST on real neuron ids.

The production part only proves that the extractor runs on MaleCNS. Seeds and targets are
chosen mechanically from the data (lowest-index neuron with enough downstream partners and
one of its hop-2 successors). The result is NOT A BIOLOGICALLY INTERPRETED CIRCUIT.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import numpy as np  # noqa: E402

from app.circuits import (  # noqa: E402
    Circuit,
    CircuitExtractor,
    ConnectivityGraph,
    ExtractorConfig,
    MaxNeuronsExceededError,
    graph_source_paths,
)
from app.config import get_settings  # noqa: E402
from app.connectome import SyntheticFixtureAdapter  # noqa: E402
from app.connectome.fixture import FIXTURE_SELECTION_RULE  # noqa: E402

TECHNICAL_LABEL = (
    "TECHNICAL EXTRACTION SMOKE TEST — NOT A BIOLOGICALLY INTERPRETED CIRCUIT. Seeds/targets "
    "were chosen mechanically from the data to prove the extractor runs on MaleCNS v1.0; "
    "no behavior, function or circuit identity is claimed."
)

# Fixture expectation: downstream from syn_001, 2 hops, min_synapses 1.
FIXTURE_EXPECTED_NODES = {
    "syn_001": 0,
    "syn_003": 1,
    "syn_004": 1,
    "syn_005": 2,
    "syn_006": 2,
    "syn_007": 2,
}
FIXTURE_EXPECTED_EDGES = {
    ("syn_001", "syn_003", 12),
    ("syn_001", "syn_004", 3),
    ("syn_003", "syn_005", 2),
    ("syn_003", "syn_006", 20),
    ("syn_004", "syn_006", 7),
    ("syn_004", "syn_007", 15),
    ("syn_005", "syn_007", 5),
    ("syn_006", "syn_003", 1),
    ("syn_007", "syn_007", 1),
}


def fixture_smoke(out_dir: Path) -> bool:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    connections = adapter.load_connections(neurons["neuron_id"]).table
    graph = ConnectivityGraph.from_tables(
        neurons, connections, selection_rule=FIXTURE_SELECTION_RULE
    )
    config = ExtractorConfig(
        seed_neuron_ids=["syn_001"],
        target_neuron_ids=["syn_007", "syn_002"],
        max_hops=2,
        min_synapses=1,
        max_neurons=50,
        direction="downstream",
    )
    circuit = CircuitExtractor(graph).extract(
        config, circuit_id="fixture_smoke_downstream", notes="synthetic fixture smoke test"
    )
    nodes = {n.neuron_id: n.minimum_hop_from_seed for n in circuit.nodes}
    edges = {(e.pre_neuron_id, e.post_neuron_id, e.synapse_count) for e in circuit.edges}
    targets = {t.neuron_id: (t.reachable, t.minimum_path_length) for t in circuit.target_neurons}
    ok = (
        nodes == FIXTURE_EXPECTED_NODES
        and edges == FIXTURE_EXPECTED_EDGES
        and targets == {"syn_007": (True, 2), "syn_002": (False, None)}
    )
    json_path, parquet_path = circuit.save(out_dir)
    reloaded = Circuit.load(json_path)
    ok = ok and reloaded.model_dump() == circuit.model_dump()
    ok = ok and Circuit.load_edges(parquet_path).num_rows == len(circuit.edges)
    print(
        f"[smoke-circuit] fixture: nodes={len(nodes)} edges={len(edges)} targets={targets} "
        f"round-trip={'ok' if ok else 'MISMATCH'} -> {'PASS' if ok else 'FAIL'}"
    )
    if not ok:
        print(f"   nodes={nodes}\n   edges={sorted(edges)}", file=sys.stderr)
    return ok


def choose_seed_and_target(graph: ConnectivityGraph, min_synapses: int) -> tuple[str, str | None]:
    """Mechanical choice: lowest-index neuron with >= 3 downstream partners at the threshold,
    and its lowest-index hop-2 successor (if any). No biological meaning."""
    extractor = CircuitExtractor(graph)
    for index in range(graph.num_nodes):
        nbrs, _ = graph.successors(index, min_synapses)
        if nbrs.size < 3:
            continue
        seed = str(graph.neuron_ids[index])
        result = extractor.traverse(
            np.array([index]),
            direction="downstream",
            max_hops=2,
            min_synapses=min_synapses,
            max_neurons=10**9,
        )
        hop2 = np.flatnonzero(result.hop == 2)
        return seed, (str(graph.neuron_ids[hop2[0]]) if hop2.size else None)
    raise RuntimeError("no neuron with >= 3 downstream partners found")


def production_smoke(processed_dir: Path, out_dir: Path, no_cache: bool) -> bool | None:
    if not (processed_dir / "neurons.parquet").is_file():
        print(f"[smoke-circuit] production: no normalized data in {processed_dir}; skipped")
        return None
    t0 = time.perf_counter()
    graph = ConnectivityGraph.load(processed_dir, use_cache=not no_cache)
    load_s = time.perf_counter() - t0
    info = graph.load_info
    print(
        f"[smoke-circuit] production graph: {graph.num_nodes:,} neurons, "
        f"{graph.num_edges:,} edges; load {load_s:.2f}s "
        f"cache_hit={info.cache_hit if info else None}; "
        f"arrays {graph.memory_bytes() / 1e6:.1f} MB"
    )
    print(f"[smoke-circuit] {TECHNICAL_LABEL}")
    extractor = CircuitExtractor(graph)
    source = graph_source_paths(processed_dir, PROJECT_ROOT)
    report: dict = {
        "label": TECHNICAL_LABEL,
        "graph": {
            "neurons": graph.num_nodes,
            "edges": graph.num_edges,
            "selection_rule": graph.selection_rule,
            "load_seconds": round(load_s, 3),
            "cache_hit": info.cache_hit if info else None,
            "strategy": info.strategy if info else None,
            "array_bytes": graph.memory_bytes(),
        },
        "runs": [],
    }
    ok = True
    for min_synapses in (10, 20, 50, 100):
        seed, target = choose_seed_and_target(graph, min_synapses)
        for direction in ("downstream", "upstream"):
            targets = [target] if target and direction == "downstream" else []
            # hop 2 first; if the hard limit aborts it (recorded), retry with hop 1
            for hops in (2, 1):
                config = ExtractorConfig(
                    seed_neuron_ids=[seed],
                    target_neuron_ids=targets,
                    max_hops=hops,
                    min_synapses=min_synapses,
                    max_neurons=2000,
                    direction=direction,
                )
                circuit_id = f"smoke_technical_{direction}_min{min_synapses}_hops{hops}"
                try:
                    circuit = extractor.extract(
                        config, circuit_id=circuit_id, notes=TECHNICAL_LABEL, graph_source=source
                    )
                except MaxNeuronsExceededError as exc:
                    print(f"[smoke-circuit] {circuit_id}: aborted as designed ({exc})")
                    report["runs"].append(
                        {
                            "circuit_id": circuit_id,
                            "config": config.model_dump(),
                            "aborted": str(exc),
                        }
                    )
                    continue
                json_path, parquet_path = circuit.save(out_dir)
                reloaded = Circuit.load(json_path)
                ok = ok and reloaded.provenance.circuit_hash == circuit.provenance.circuit_hash
                s = circuit.stats
                shown_target = target if direction == "downstream" else "-"
                target_summary = [
                    (t.neuron_id, t.reachable, t.minimum_path_length)
                    for t in circuit.target_neurons
                ]
                print(
                    f"[smoke-circuit] {circuit_id}: seed={seed} target={shown_target} "
                    f"visited={s.visited_neurons:,} returned neurons={s.returned_neurons:,} "
                    f"edges={s.returned_edges:,} examined={s.examined_edges:,} "
                    f"time={s.extraction_seconds:.3f}s targets={target_summary}"
                )
                report["runs"].append(
                    {
                        "circuit_id": circuit_id,
                        "config": config.model_dump(),
                        "stats": s.model_dump(),
                        "targets": [t.model_dump() for t in circuit.target_neurons],
                        "circuit_hash": circuit.provenance.circuit_hash,
                        "json": (
                            str(json_path.relative_to(PROJECT_ROOT))
                            if json_path.is_relative_to(PROJECT_ROOT)
                            else str(json_path)
                        ),
                    }
                )
                break
        if any("stats" in run for run in report["runs"]):
            break  # one successful threshold is enough for the smoke test
    report_path = out_dir / "smoke_technical_extraction.perf.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    succeeded = ok and any("stats" in r for r in report["runs"])
    print(
        f"[smoke-circuit] production: {'PASS' if succeeded else 'FAIL'}; "
        f"performance report -> {report_path}"
    )
    return ok and any("stats" in r for r in report["runs"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--fixture-only", action="store_true")
    parser.add_argument("--processed-dir")
    parser.add_argument("--out-dir", help="artifact directory (default data/circuits)")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    out_dir = Path(args.out_dir) if args.out_dir else settings.circuits_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = fixture_smoke(out_dir)
    if not args.fixture_only:
        processed_dir = (
            Path(args.processed_dir) if args.processed_dir else settings.processed_data_dir
        )
        production = production_smoke(processed_dir, out_dir, args.no_cache)
        ok = ok and (production is not False)
    print(f"[smoke-circuit] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
