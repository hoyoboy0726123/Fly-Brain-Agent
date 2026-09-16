"""Canonical simulation graph as a compact directed adjacency structure.

BIOLOGICAL STRUCTURE layer. The graph is built from ``neurons.parquet`` and
``connections.parquet`` (the canonical simulation graph, DATA.md §8) and stored as two
CSR-style arrays: out-edges grouped by presynaptic neuron and in-edges grouped by
postsynaptic neuron. No NetworkX object is created for the full graph.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.circuits.errors import GraphBuildError, MissingNeuronError
from app.connectome.provenance import Provenance
from app.connectome.schema import validate_connections_table, validate_neurons_table

Direction = Literal["downstream", "upstream"]

CACHE_FORMAT = 1
CACHE_ARRAYS = (
    "out_indptr",
    "out_indices",
    "out_weights",
    "in_indptr",
    "in_indices",
    "in_weights",
    "neuron_ids",
)
NODE_METADATA_COLUMNS = ("cell_type", "cell_class", "neurotransmitter")


@dataclass(frozen=True)
class GraphLoadInfo:
    """How the graph was obtained (for performance reports)."""

    load_seconds: float
    cache_hit: bool
    cache_dir: Path | None
    strategy: str


class ConnectivityGraph:
    """Directed weighted graph over the canonical neuron set (CSR out + CSR in)."""

    def __init__(
        self,
        *,
        neuron_ids: np.ndarray,
        out_indptr: np.ndarray,
        out_indices: np.ndarray,
        out_weights: np.ndarray,
        in_indptr: np.ndarray,
        in_indices: np.ndarray,
        in_weights: np.ndarray,
        dataset: str,
        dataset_version: str,
        selection_rule: str,
        neurons: pa.Table | None = None,
        provenance: Provenance | None = None,
        load_info: GraphLoadInfo | None = None,
    ) -> None:
        self.neuron_ids = neuron_ids
        self.out_indptr = out_indptr
        self.out_indices = out_indices
        self.out_weights = out_weights
        self.in_indptr = in_indptr
        self.in_indices = in_indices
        self.in_weights = in_weights
        self.dataset = dataset
        self.dataset_version = dataset_version
        self.selection_rule = selection_rule
        self.neurons = neurons
        self.provenance = provenance
        self.load_info = load_info
        self._index: dict[str, int] = {str(nid): i for i, nid in enumerate(neuron_ids.tolist())}

    # ------------------------------------------------------------------ properties
    @property
    def num_nodes(self) -> int:
        return int(self.neuron_ids.shape[0])

    @property
    def num_edges(self) -> int:
        return int(self.out_indices.shape[0])

    def memory_bytes(self) -> int:
        """Bytes held by the adjacency arrays (index dict and metadata table excluded)."""
        arrays = (
            self.out_indptr,
            self.out_indices,
            self.out_weights,
            self.in_indptr,
            self.in_indices,
            self.in_weights,
            self.neuron_ids,
        )
        return int(sum(a.nbytes for a in arrays))

    # ------------------------------------------------------------------ lookups
    def index_of(self, neuron_id: str) -> int:
        try:
            return self._index[str(neuron_id)]
        except KeyError:
            raise MissingNeuronError("requested", [str(neuron_id)]) from None

    def resolve(self, neuron_ids: list[str] | tuple[str, ...], role: str) -> np.ndarray:
        """Map identifiers to sorted unique indices; fail loudly listing every missing id."""
        missing = [nid for nid in neuron_ids if str(nid) not in self._index]
        if missing:
            raise MissingNeuronError(role, missing)
        indices = np.fromiter((self._index[str(nid)] for nid in neuron_ids), dtype=np.int64)
        return np.unique(indices)

    def ids_of(self, indices: np.ndarray) -> list[str]:
        return [str(x) for x in self.neuron_ids[np.asarray(indices, dtype=np.int64)].tolist()]

    def successors(self, index: int, min_synapses: int = 0) -> tuple[np.ndarray, np.ndarray]:
        start, end = int(self.out_indptr[index]), int(self.out_indptr[index + 1])
        nbrs, weights = self.out_indices[start:end], self.out_weights[start:end]
        if min_synapses > 0:
            mask = weights >= min_synapses
            return nbrs[mask], weights[mask]
        return nbrs, weights

    def predecessors(self, index: int, min_synapses: int = 0) -> tuple[np.ndarray, np.ndarray]:
        start, end = int(self.in_indptr[index]), int(self.in_indptr[index + 1])
        nbrs, weights = self.in_indices[start:end], self.in_weights[start:end]
        if min_synapses > 0:
            mask = weights >= min_synapses
            return nbrs[mask], weights[mask]
        return nbrs, weights

    def neighbors(
        self, index: int, direction: Direction, min_synapses: int = 0
    ) -> tuple[np.ndarray, np.ndarray]:
        if direction == "downstream":
            return self.successors(index, min_synapses)
        if direction == "upstream":
            return self.predecessors(index, min_synapses)
        raise ValueError(f"unknown direction {direction!r}")

    def degree(self, index: int, direction: Direction) -> int:
        indptr = self.out_indptr if direction == "downstream" else self.in_indptr
        return int(indptr[index + 1] - indptr[index])

    def edge_weight(self, pre_index: int, post_index: int) -> int | None:
        nbrs, weights = self.successors(pre_index)
        position = np.searchsorted(nbrs, post_index)
        if position < nbrs.shape[0] and nbrs[position] == post_index:
            return int(weights[position])
        return None

    def node_metadata(self, indices: np.ndarray) -> dict[str, list[Any]]:
        """Nullable SDD annotation columns for the given node indices (from neurons.parquet)."""
        result: dict[str, list[Any]] = {}
        if self.neurons is None:
            return {name: [None] * len(indices) for name in NODE_METADATA_COLUMNS}
        take = pa.array(np.asarray(indices, dtype=np.int64))
        for name in NODE_METADATA_COLUMNS:
            if name in self.neurons.column_names:
                result[name] = self.neurons.column(name).take(take).to_pylist()
            else:
                result[name] = [None] * len(indices)
        return result

    def fingerprint(self) -> str:
        """Stable identifier of the graph content this extractor ran on."""
        payload: dict[str, Any] = {
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "selection_rule": self.selection_rule,
            "num_nodes": self.num_nodes,
            "num_edges": self.num_edges,
            "weight_sum": int(self.out_weights.sum(dtype=np.int64)),
        }
        if self.provenance is not None:
            payload["raw_files"] = [
                {"role": f.role, "sha256": f.sha256} for f in self.provenance.raw_files
            ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_tables(
        cls,
        neurons: pa.Table,
        connections: pa.Table,
        *,
        selection_rule: str | None = None,
        provenance: Provenance | None = None,
        load_info: GraphLoadInfo | None = None,
    ) -> ConnectivityGraph:
        validate_neurons_table(neurons)
        validate_connections_table(connections)
        ids = neurons["neuron_id"]
        if pc.count_distinct(ids).as_py() != neurons.num_rows:
            raise GraphBuildError("neuron_id must be unique in the neurons table")

        dataset, dataset_version = (
            _single_value(neurons, "dataset"),
            _single_value(neurons, "dataset_version"),
        )
        if connections.num_rows:
            if _single_value(connections, "dataset") != dataset:
                raise GraphBuildError("connections.dataset differs from neurons.dataset")
            if _single_value(connections, "dataset_version") != dataset_version:
                raise GraphBuildError(
                    "connections.dataset_version differs from neurons.dataset_version"
                )

        id_array = pa.array(ids.to_pylist() if isinstance(ids, pa.ChunkedArray) else ids)
        pre = pc.index_in(connections["pre_neuron_id"], value_set=id_array)
        post = pc.index_in(connections["post_neuron_id"], value_set=id_array)
        if pre.null_count or post.null_count:
            missing_pre = pc.unique(connections["pre_neuron_id"].filter(pc.is_null(pre)))
            missing_post = pc.unique(connections["post_neuron_id"].filter(pc.is_null(post)))
            sample = (missing_pre.to_pylist() + missing_post.to_pylist())[:10]
            raise GraphBuildError(
                f"{pre.null_count + post.null_count} edge endpoint(s) reference neurons missing "
                f"from the neurons table, e.g. {sample}"
            )
        pre_idx = pre.to_numpy(zero_copy_only=False).astype(np.int64)
        post_idx = post.to_numpy(zero_copy_only=False).astype(np.int64)
        weights64 = connections["synapse_count"].to_numpy(zero_copy_only=False).astype(np.int64)
        if weights64.size and weights64.max() > np.iinfo(np.int32).max:
            raise GraphBuildError("synapse_count exceeds int32 range")
        weights = weights64.astype(np.int32)

        n = neurons.num_rows
        order_out = np.lexsort((post_idx, pre_idx))
        pre_sorted, post_sorted = pre_idx[order_out], post_idx[order_out]
        if pre_sorted.size > 1:
            duplicate = (pre_sorted[1:] == pre_sorted[:-1]) & (post_sorted[1:] == post_sorted[:-1])
            if duplicate.any():
                position = int(np.flatnonzero(duplicate)[0])
                pre_id = id_array[int(pre_sorted[position])]
                post_id = id_array[int(post_sorted[position])]
                raise GraphBuildError(f"duplicate directed edge {pre_id} -> {post_id}")
        out_indptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(np.bincount(pre_idx, minlength=n), out=out_indptr[1:])
        order_in = np.lexsort((pre_idx, post_idx))
        in_indptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(np.bincount(post_idx, minlength=n), out=in_indptr[1:])

        return cls(
            neuron_ids=np.array(id_array.to_pylist(), dtype=str),
            out_indptr=out_indptr,
            out_indices=post_sorted.astype(np.int32),
            out_weights=weights[order_out],
            in_indptr=in_indptr,
            in_indices=pre_idx[order_in].astype(np.int32),
            in_weights=weights[order_in],
            dataset=dataset,
            dataset_version=dataset_version,
            selection_rule=selection_rule or "unknown (no provenance supplied)",
            neurons=neurons,
            provenance=provenance,
            load_info=load_info,
        )

    @classmethod
    def load(
        cls,
        processed_dir: Path,
        *,
        use_cache: bool = True,
        cache_dir: Path | None = None,
    ) -> ConnectivityGraph:
        """Load the canonical graph from ``processed_dir`` (optionally via an ``.npy`` cache)."""
        started = time.perf_counter()
        processed_dir = Path(processed_dir)
        neurons_path = processed_dir / "neurons.parquet"
        connections_path = processed_dir / "connections.parquet"
        provenance_path = processed_dir / "provenance.json"
        for path in (neurons_path, connections_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        provenance = Provenance.read(provenance_path) if provenance_path.is_file() else None
        selection_rule = (
            provenance.canonical_graph.selection_rule
            if provenance is not None and provenance.canonical_graph is not None
            else None
        )
        cache_dir = cache_dir if cache_dir is not None else processed_dir / "graph_cache"
        neurons = pq.read_table(neurons_path)

        if use_cache:
            cached = _load_cache(cache_dir, processed_dir)
            if cached is not None:
                arrays, meta = cached
                info = GraphLoadInfo(
                    load_seconds=time.perf_counter() - started,
                    cache_hit=True,
                    cache_dir=cache_dir,
                    strategy="neurons.parquet + memory-mapped .npy CSR cache",
                )
                return cls(
                    neuron_ids=arrays["neuron_ids"],
                    out_indptr=arrays["out_indptr"],
                    out_indices=arrays["out_indices"],
                    out_weights=arrays["out_weights"],
                    in_indptr=arrays["in_indptr"],
                    in_indices=arrays["in_indices"],
                    in_weights=arrays["in_weights"],
                    dataset=meta["dataset"],
                    dataset_version=meta["dataset_version"],
                    selection_rule=meta["selection_rule"],
                    neurons=neurons,
                    provenance=provenance,
                    load_info=info,
                )

        connections = pq.read_table(connections_path)
        graph = cls.from_tables(
            neurons, connections, selection_rule=selection_rule, provenance=provenance
        )
        if use_cache:
            _save_cache(cache_dir, processed_dir, graph)
        graph.load_info = GraphLoadInfo(
            load_seconds=time.perf_counter() - started,
            cache_hit=False,
            cache_dir=cache_dir if use_cache else None,
            strategy="parquet -> pyarrow index_in -> numpy lexsort CSR (out) + CSR (in)",
        )
        return graph


# ---------------------------------------------------------------------------- helpers
def _single_value(table: pa.Table, column: str) -> str:
    values = pc.unique(table[column])
    if len(values) != 1:
        raise GraphBuildError(f"column {column!r} must hold exactly one value, found {len(values)}")
    return str(values[0].as_py())


def _file_stamp(processed_dir: Path) -> dict[str, dict[str, int]]:
    stamp: dict[str, dict[str, int]] = {}
    for name in ("neurons.parquet", "connections.parquet", "provenance.json"):
        path = processed_dir / name
        if path.is_file():
            stat = path.stat()
            stamp[name] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return stamp


def _save_cache(cache_dir: Path, processed_dir: Path, graph: ConnectivityGraph) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in CACHE_ARRAYS:
        np.save(cache_dir / f"{name}.npy", getattr(graph, name))
    meta = {
        "format": CACHE_FORMAT,
        "files": _file_stamp(processed_dir),
        "dataset": graph.dataset,
        "dataset_version": graph.dataset_version,
        "selection_rule": graph.selection_rule,
        "num_nodes": graph.num_nodes,
        "num_edges": graph.num_edges,
    }
    (cache_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")


def _load_cache(
    cache_dir: Path, processed_dir: Path
) -> tuple[dict[str, np.ndarray], dict[str, Any]] | None:
    meta_path = cache_dir / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text())
    except ValueError:
        return None
    if meta.get("format") != CACHE_FORMAT or meta.get("files") != _file_stamp(processed_dir):
        return None
    arrays: dict[str, np.ndarray] = {}
    for name in CACHE_ARRAYS:
        path = cache_dir / f"{name}.npy"
        if not path.is_file():
            return None
        arrays[name] = np.load(path, mmap_mode="r")
    return arrays, meta
