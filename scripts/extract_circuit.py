#!/usr/bin/env python3
"""Extract a bounded circuit from the canonical simulation graph (P2).

    scripts/extract_circuit.py --circuit-id demo --seeds 10001 --targets 10005 \\
        --max-hops 2 --min-synapses 10 --max-neurons 2000 --direction downstream

    scripts/extract_circuit.py --fixture --circuit-id fx --seeds syn_001 --max-hops 2 \\
        --min-synapses 1 --max-neurons 50 --out-dir /tmp/circuits

Writes data/circuits/<circuit_id>.json and .parquet (or --out-dir). The artifact is a
structural subgraph; it carries no behavioral or functional claim.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.circuits import (  # noqa: E402
    CircuitExtractionError,
    CircuitExtractor,
    ConnectivityGraph,
    ExtractorConfig,
    graph_source_paths,
)
from app.config import get_settings  # noqa: E402
from app.connectome import SyntheticFixtureAdapter  # noqa: E402
from app.connectome.fixture import FIXTURE_SELECTION_RULE  # noqa: E402


def load_graph(args: argparse.Namespace) -> tuple[ConnectivityGraph, dict[str, str | None]]:
    if args.fixture:
        adapter = SyntheticFixtureAdapter()
        neurons = adapter.load_neurons()
        connections = adapter.load_connections(neurons["neuron_id"]).table
        graph = ConnectivityGraph.from_tables(
            neurons, connections, selection_rule=FIXTURE_SELECTION_RULE
        )
        return graph, {"fixture": str(adapter.path.relative_to(PROJECT_ROOT))}
    processed_dir = (
        Path(args.processed_dir) if args.processed_dir else get_settings().processed_data_dir
    )
    graph = ConnectivityGraph.load(processed_dir, use_cache=not args.no_cache)
    return graph, graph_source_paths(processed_dir, PROJECT_ROOT)


def print_report(circuit) -> None:
    stats = circuit.stats
    graph_ref = circuit.canonical_graph
    print(
        f"[extract] circuit_id={circuit.circuit_id} dataset={circuit.dataset} "
        f"{circuit.dataset_version}"
    )
    print(
        f"[extract] canonical graph: {graph_ref.selection_rule} "
        f"({graph_ref.neuron_count:,} neurons, {graph_ref.connection_count:,} edges)"
    )
    print(
        f"[extract] graph load: {stats.graph_load_seconds}s cache_hit={stats.graph_cache_hit} "
        f"strategy={stats.graph_strategy}"
    )
    memory = f"{stats.graph_memory_bytes / 1e6:.1f} MB" if stats.graph_memory_bytes else "n/a"
    rss = f"{stats.process_max_rss_bytes / 1e6:.1f} MB" if stats.process_max_rss_bytes else "n/a"
    print(f"[extract] graph arrays: {memory}; process max RSS: {rss}")
    print(
        f"[extract] extraction: {stats.extraction_seconds}s visited={stats.visited_neurons:,} "
        f"returned neurons={stats.returned_neurons:,} edges={stats.returned_edges:,} "
        f"examined edges={stats.examined_edges:,}"
    )
    for target in circuit.target_neurons:
        print(
            f"[extract] target {target.neuron_id}: reachable={target.reachable} "
            f"minimum_path_length={target.minimum_path_length}"
        )
    print(f"[extract] circuit_hash={circuit.provenance.circuit_hash}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--circuit-id", required=True)
    parser.add_argument("--seeds", nargs="+", required=True, help="seed neuron ids")
    parser.add_argument("--targets", nargs="*", default=[], help="target neuron ids (optional)")
    parser.add_argument("--max-hops", type=int, required=True)
    parser.add_argument("--min-synapses", type=int, required=True)
    parser.add_argument(
        "--max-neurons", type=int, required=True, help="HARD limit; abort if exceeded"
    )
    parser.add_argument("--direction", choices=("downstream", "upstream"), default="downstream")
    parser.add_argument(
        "--restrict-to-target-paths",
        action="store_true",
        help="keep only neurons on a seed->target path of length <= max_hops",
    )
    parser.add_argument(
        "--notes", default="", help="free-text note stored in the artifact provenance"
    )
    parser.add_argument("--fixture", action="store_true", help="use the synthetic fixture graph")
    parser.add_argument(
        "--processed-dir",
        help="directory with neurons/connections parquet (default data/processed)",
    )
    parser.add_argument("--out-dir", help="artifact directory (default data/circuits)")
    parser.add_argument(
        "--no-cache", action="store_true", help="do not read/write the .npy graph cache"
    )
    args = parser.parse_args(argv)

    try:
        config = ExtractorConfig(
            seed_neuron_ids=args.seeds,
            target_neuron_ids=args.targets,
            max_hops=args.max_hops,
            min_synapses=args.min_synapses,
            max_neurons=args.max_neurons,
            direction=args.direction,
            restrict_to_target_paths=args.restrict_to_target_paths,
        )
        graph, source = load_graph(args)
        circuit = CircuitExtractor(graph).extract(
            config, circuit_id=args.circuit_id, notes=args.notes, graph_source=source
        )
    except (CircuitExtractionError, FileNotFoundError, ValueError) as exc:
        print(f"[extract] FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else get_settings().circuits_data_dir
    json_path, parquet_path = circuit.save(out_dir)
    print_report(circuit)
    print(f"[extract] wrote {json_path}")
    print(f"[extract] wrote {parquet_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
