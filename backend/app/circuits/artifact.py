"""Circuit artifact (SDD §4): JSON + Parquet export/import with integrity hash.

Every edge carries the five provenance columns of ``connections.parquet``; edges are copied
from the canonical graph and never synthesized.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, field_validator, model_validator

from app.circuits.errors import ArtifactIntegrityError
from app.connectome.schema import connections_schema, validate_connections_table

CIRCUIT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
Direction = Literal["downstream", "upstream"]


class ExtractorConfig(BaseModel):
    """Inputs of ``CircuitExtractor.extract`` (identifiers are deduplicated and sorted)."""

    seed_neuron_ids: list[str] = Field(min_length=1)
    target_neuron_ids: list[str] = Field(default_factory=list)
    max_hops: int = Field(ge=0)
    min_synapses: int = Field(ge=0)
    max_neurons: int = Field(ge=1)
    direction: Direction = "downstream"
    #: Optional pruning to neurons lying on a seed→target path of length ≤ max_hops.
    restrict_to_target_paths: bool = False

    @field_validator("seed_neuron_ids", "target_neuron_ids", mode="before")
    @classmethod
    def _canonical_ids(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        return sorted({str(item) for item in value})

    @model_validator(mode="after")
    def _paths_need_targets(self) -> ExtractorConfig:
        if self.restrict_to_target_paths and not self.target_neuron_ids:
            raise ValueError("restrict_to_target_paths requires at least one target neuron id")
        return self


class CanonicalGraphRef(BaseModel):
    selection_rule: str
    neuron_count: int
    connection_count: int
    fingerprint: str


class CircuitNode(BaseModel):
    neuron_id: str
    minimum_hop_from_seed: int = Field(ge=0)
    is_seed: bool
    is_target: bool
    cell_type: str | None = None
    cell_class: str | None = None
    neurotransmitter: str | None = None


class CircuitEdge(BaseModel):
    pre_neuron_id: str
    post_neuron_id: str
    synapse_count: int = Field(ge=0)
    dataset: str
    dataset_version: str


class TargetReport(BaseModel):
    neuron_id: str
    reachable: bool
    minimum_path_length: int | None = None

    @model_validator(mode="after")
    def _consistent(self) -> TargetReport:
        if self.reachable and self.minimum_path_length is None:
            raise ValueError("reachable target must have minimum_path_length")
        if not self.reachable and self.minimum_path_length is not None:
            raise ValueError("unreachable target must not carry a path length")
        return self


class ExtractionStats(BaseModel):
    visited_neurons: int
    returned_neurons: int
    returned_edges: int
    examined_edges: int
    extraction_seconds: float
    graph_load_seconds: float | None = None
    graph_cache_hit: bool | None = None
    graph_memory_bytes: int | None = None
    process_max_rss_bytes: int | None = None
    graph_strategy: str | None = None


class CircuitProvenance(BaseModel):
    extracted_at: str
    extractor_version: str
    graph_fingerprint: str
    graph_source: dict[str, str | None] = Field(default_factory=dict)
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    circuit_hash: str = ""
    notes: str = ""
    biological_interpretation: str = (
        "NONE. This artifact is a structural subgraph of the canonical simulation graph "
        "selected purely by the extractor configuration. It carries no behavioral or "
        "functional claim."
    )


class Circuit(BaseModel):
    """SDD §4 artifact plus canonical-graph reference, statistics and provenance."""

    circuit_id: str
    dataset: str
    dataset_version: str
    canonical_graph: CanonicalGraphRef
    extractor_config: ExtractorConfig
    seed_neurons: list[str]
    target_neurons: list[TargetReport]
    nodes: list[CircuitNode]
    edges: list[CircuitEdge]
    stats: ExtractionStats
    provenance: CircuitProvenance

    @field_validator("circuit_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not CIRCUIT_ID_PATTERN.match(value):
            raise ValueError(
                "circuit_id must be 1-100 chars of letters, digits, '_', '.', '-' and start "
                "with a letter or digit"
            )
        return value

    # ------------------------------------------------------------------ integrity
    def compute_hash(self) -> str:
        payload = {
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "selection_rule": self.canonical_graph.selection_rule,
            "extractor_config": self.extractor_config.model_dump(mode="json"),
            "nodes": [n.model_dump(mode="json") for n in self.nodes],
            "edges": [e.model_dump(mode="json") for e in self.edges],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def seal(self) -> Circuit:
        self.provenance.circuit_hash = self.compute_hash()
        return self

    def verify(self) -> None:
        expected = self.provenance.circuit_hash
        actual = self.compute_hash()
        if expected != actual:
            raise ArtifactIntegrityError(
                f"circuit {self.circuit_id}: recorded hash {expected[:12]}… does not match "
                f"content hash {actual[:12]}…"
            )
        for edge in self.edges:
            if edge.dataset != self.dataset or edge.dataset_version != self.dataset_version:
                raise ArtifactIntegrityError(
                    f"circuit {self.circuit_id}: edge {edge.pre_neuron_id}->{edge.post_neuron_id} "
                    "carries a different dataset/version than the circuit"
                )

    # ------------------------------------------------------------------ tables / I/O
    def edges_table(self) -> pa.Table:
        table = pa.table(
            {
                "pre_neuron_id": pa.array([e.pre_neuron_id for e in self.edges], pa.string()),
                "post_neuron_id": pa.array([e.post_neuron_id for e in self.edges], pa.string()),
                "synapse_count": pa.array([e.synapse_count for e in self.edges], pa.int64()),
                "dataset": pa.array([e.dataset for e in self.edges], pa.string()),
                "dataset_version": pa.array([e.dataset_version for e in self.edges], pa.string()),
            }
        ).cast(connections_schema())
        validate_connections_table(table)
        return table.replace_schema_metadata(
            {
                b"flybrain.circuit_id": self.circuit_id.encode(),
                b"flybrain.circuit_hash": self.provenance.circuit_hash.encode(),
                b"flybrain.extractor_config": json.dumps(
                    self.extractor_config.model_dump(mode="json"), sort_keys=True
                ).encode(),
                b"flybrain.canonical_graph.selection_rule": (
                    self.canonical_graph.selection_rule.encode()
                ),
            }
        )

    def nodes_table(self) -> pa.Table:
        return pa.table(
            {
                "neuron_id": pa.array([n.neuron_id for n in self.nodes], pa.string()),
                "minimum_hop_from_seed": pa.array(
                    [n.minimum_hop_from_seed for n in self.nodes], pa.int32()
                ),
                "is_seed": pa.array([n.is_seed for n in self.nodes], pa.bool_()),
                "is_target": pa.array([n.is_target for n in self.nodes], pa.bool_()),
            }
        )

    def json_path(self, out_dir: Path) -> Path:
        return Path(out_dir) / f"{self.circuit_id}.json"

    def parquet_path(self, out_dir: Path) -> Path:
        return Path(out_dir) / f"{self.circuit_id}.parquet"

    def save(self, out_dir: Path) -> tuple[Path, Path]:
        """Write ``<circuit_id>.json`` (full artifact) and ``<circuit_id>.parquet`` (edges)."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if not self.provenance.circuit_hash:
            self.seal()
        self.verify()
        json_path, parquet_path = self.json_path(out_dir), self.parquet_path(out_dir)
        json_path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        )
        pq.write_table(self.edges_table(), parquet_path, compression="zstd")
        return json_path, parquet_path

    @classmethod
    def load(cls, json_path: Path, *, verify: bool = True) -> Circuit:
        circuit = cls.model_validate_json(Path(json_path).read_text())
        if verify:
            circuit.verify()
        return circuit

    @staticmethod
    def load_edges(parquet_path: Path) -> pa.Table:
        table = pq.read_table(parquet_path)
        validate_connections_table(table)
        return table
