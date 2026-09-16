"""Deterministic bounded circuit extraction over the canonical simulation graph.

Algorithm (per direction): multi-source breadth-first traversal from the seed set, one hop
level at a time, following out-edges (downstream) or in-edges (upstream) whose
``synapse_count >= min_synapses``. ``max_neurons`` is a hard limit: the traversal aborts
with ``MaxNeuronsExceededError`` *before* adding a hop level that would exceed it. The
returned circuit is the subgraph induced by the discovered neurons: every directed edge of
the canonical graph between two included neurons that passes the threshold. Edges are
copied verbatim from the graph, never synthesized.
"""

from __future__ import annotations

import resource
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app import __version__
from app.circuits.artifact import (
    CanonicalGraphRef,
    Circuit,
    CircuitEdge,
    CircuitNode,
    CircuitProvenance,
    ExtractionStats,
    ExtractorConfig,
    TargetReport,
)
from app.circuits.errors import MaxNeuronsExceededError
from app.circuits.graph import ConnectivityGraph, Direction

OPPOSITE: dict[str, Direction] = {"downstream": "upstream", "upstream": "downstream"}


@dataclass(frozen=True)
class TraversalResult:
    """Hop distances from the source set (-1 = not reached) and traversal counters."""

    hop: np.ndarray
    discovered: int
    examined_edges: int

    def reached(self) -> np.ndarray:
        return np.flatnonzero(self.hop >= 0)


class CircuitExtractor:
    """Extracts bounded, provenance-preserving circuits from a ``ConnectivityGraph``."""

    def __init__(self, graph: ConnectivityGraph) -> None:
        self.graph = graph

    # ------------------------------------------------------------------ traversal
    def traverse(
        self,
        sources: np.ndarray,
        *,
        direction: Direction,
        max_hops: int,
        min_synapses: int,
        max_neurons: int,
    ) -> TraversalResult:
        graph = self.graph
        hop = np.full(graph.num_nodes, -1, dtype=np.int32)
        sources = np.unique(np.asarray(sources, dtype=np.int64))
        if sources.size > max_neurons:
            raise MaxNeuronsExceededError(max_neurons, int(sources.size), hop=0)
        hop[sources] = 0
        discovered = int(sources.size)
        examined = 0
        frontier = sources
        for level in range(1, max_hops + 1):
            if frontier.size == 0:
                break
            parts: list[np.ndarray] = []
            for node in frontier.tolist():
                examined += graph.degree(node, direction)
                nbrs, _ = graph.neighbors(node, direction, min_synapses)
                if nbrs.size:
                    parts.append(nbrs)
            if not parts:
                break
            candidates = np.unique(np.concatenate(parts).astype(np.int64))
            new = candidates[hop[candidates] < 0]
            if discovered + new.size > max_neurons:
                raise MaxNeuronsExceededError(max_neurons, discovered + int(new.size), hop=level)
            hop[new] = level
            discovered += int(new.size)
            frontier = new
        return TraversalResult(hop=hop, discovered=discovered, examined_edges=examined)

    # ------------------------------------------------------------------ extraction
    def extract(
        self,
        config: ExtractorConfig,
        *,
        circuit_id: str,
        notes: str = "",
        graph_source: dict[str, str | None] | None = None,
    ) -> Circuit:
        graph = self.graph
        started = time.perf_counter()

        seeds = graph.resolve(config.seed_neuron_ids, "seed")
        targets = (
            graph.resolve(config.target_neuron_ids, "target")
            if config.target_neuron_ids
            else np.array([], dtype=np.int64)
        )

        forward = self.traverse(
            seeds,
            direction=config.direction,
            max_hops=config.max_hops,
            min_synapses=config.min_synapses,
            max_neurons=config.max_neurons,
        )
        hop = forward.hop
        included = hop >= 0
        examined = forward.examined_edges

        if config.restrict_to_target_paths:
            backward = self.traverse(
                targets,
                direction=OPPOSITE[config.direction],
                max_hops=config.max_hops,
                min_synapses=config.min_synapses,
                max_neurons=config.max_neurons,
            )
            examined += backward.examined_edges
            on_path = included & (backward.hop >= 0) & ((hop + backward.hop) <= config.max_hops)
            included = on_path

        node_indices = np.flatnonzero(included)
        node_indices = node_indices[np.lexsort((node_indices, hop[node_indices]))]
        edges = self._induced_edges(node_indices, included, config.min_synapses)

        seed_set = set(seeds.tolist())
        target_set = set(targets.tolist())
        metadata = graph.node_metadata(node_indices)
        node_ids = graph.ids_of(node_indices)
        nodes = [
            CircuitNode(
                neuron_id=node_ids[i],
                minimum_hop_from_seed=int(hop[idx]),
                is_seed=int(idx) in seed_set,
                is_target=int(idx) in target_set,
                cell_type=metadata["cell_type"][i],
                cell_class=metadata["cell_class"][i],
                neurotransmitter=metadata["neurotransmitter"][i],
            )
            for i, idx in enumerate(node_indices.tolist())
        ]
        target_reports = [
            TargetReport(
                neuron_id=str(graph.neuron_ids[t]),
                reachable=bool(hop[t] >= 0),
                minimum_path_length=int(hop[t]) if hop[t] >= 0 else None,
            )
            for t in targets.tolist()
        ]

        elapsed = time.perf_counter() - started
        load_info = graph.load_info
        stats = ExtractionStats(
            visited_neurons=forward.discovered,
            returned_neurons=len(nodes),
            returned_edges=len(edges),
            examined_edges=examined,
            extraction_seconds=round(elapsed, 6),
            graph_load_seconds=round(load_info.load_seconds, 6) if load_info else None,
            graph_cache_hit=load_info.cache_hit if load_info else None,
            graph_memory_bytes=graph.memory_bytes(),
            process_max_rss_bytes=_max_rss_bytes(),
            graph_strategy=load_info.strategy if load_info else "in-memory tables",
        )
        provenance = CircuitProvenance(
            extracted_at=datetime.now(UTC).isoformat(timespec="seconds"),
            extractor_version=__version__,
            graph_fingerprint=graph.fingerprint(),
            graph_source=graph_source or {},
            source_provenance=_source_provenance(graph),
            notes=notes,
        )
        circuit = Circuit(
            circuit_id=circuit_id,
            dataset=graph.dataset,
            dataset_version=graph.dataset_version,
            canonical_graph=CanonicalGraphRef(
                selection_rule=graph.selection_rule,
                neuron_count=graph.num_nodes,
                connection_count=graph.num_edges,
                fingerprint=graph.fingerprint(),
            ),
            extractor_config=config,
            seed_neurons=graph.ids_of(seeds),
            target_neurons=target_reports,
            nodes=nodes,
            edges=edges,
            stats=stats,
            provenance=provenance,
        )
        return circuit.seal()

    def _induced_edges(
        self, node_indices: np.ndarray, included: np.ndarray, min_synapses: int
    ) -> list[CircuitEdge]:
        graph = self.graph
        edges: list[CircuitEdge] = []
        for pre in np.sort(node_indices).tolist():
            nbrs, weights = graph.successors(pre, min_synapses)
            mask = included[nbrs]
            if not mask.any():
                continue
            pre_id = str(graph.neuron_ids[pre])
            for post, weight in zip(nbrs[mask].tolist(), weights[mask].tolist(), strict=True):
                edges.append(
                    CircuitEdge(
                        pre_neuron_id=pre_id,
                        post_neuron_id=str(graph.neuron_ids[post]),
                        synapse_count=int(weight),
                        dataset=graph.dataset,
                        dataset_version=graph.dataset_version,
                    )
                )
        return edges


# ---------------------------------------------------------------------------- helpers
def _max_rss_bytes() -> int | None:
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (OSError, ValueError):
        return None
    return int(rss) if sys.platform == "darwin" else int(rss) * 1024


def _source_provenance(graph: ConnectivityGraph) -> dict:
    provenance = graph.provenance
    if provenance is None:
        return {"available": False}
    return {
        "available": True,
        "dataset_name": provenance.dataset_name,
        "dataset_version": provenance.dataset_version,
        "license": provenance.license,
        "source_page": provenance.source_page,
        "download_url": provenance.download_url,
        "synthetic": provenance.synthetic,
        "source_dataset": (
            provenance.source_dataset.model_dump(mode="json") if provenance.source_dataset else None
        ),
        "canonical_graph": (
            provenance.canonical_graph.model_dump(mode="json")
            if provenance.canonical_graph
            else None
        ),
        "raw_files": [
            {"role": f.role, "path": f.path, "sha256": f.sha256} for f in provenance.raw_files
        ],
    }


def graph_source_paths(
    processed_dir: Path, project_root: Path | None = None
) -> dict[str, str | None]:
    """Relative paths of the tables a graph was loaded from (for artifact provenance)."""
    result: dict[str, str | None] = {}
    for key, name in (
        ("neurons", "neurons.parquet"),
        ("connections", "connections.parquet"),
        ("provenance", "provenance.json"),
    ):
        path = Path(processed_dir) / name
        if not path.is_file():
            result[key] = None
            continue
        if project_root is not None and path.resolve().is_relative_to(project_root.resolve()):
            result[key] = str(path.resolve().relative_to(project_root.resolve()))
        else:
            result[key] = str(path)
    return result
