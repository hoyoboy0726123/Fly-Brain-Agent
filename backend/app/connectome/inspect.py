"""Data validation report (DATA.md §7) computed over normalized tables."""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from pydantic import BaseModel, Field

from app.connectome.provenance import CanonicalGraph, SourceDataset
from app.connectome.schema import NEURON_REQUIRED_COLUMNS

SAMPLE_LIMIT = 10


class SynapseCountStats(BaseModel):
    min: int | None
    max: int | None
    median: float | None
    total: int


class DanglingSummary(BaseModel):
    pre_missing: int
    post_missing: int
    either_missing: int
    sample_missing_ids: list[str] = Field(default_factory=list)


class DuplicateSummary(BaseModel):
    duplicate_neuron_ids: int
    duplicate_neuron_rows: int
    sample_duplicate_neuron_ids: list[str] = Field(default_factory=list)
    duplicate_edge_pairs: int


class AnnotationColumn(BaseModel):
    name: str
    non_null: int
    distinct: int | None


class InspectionReport(BaseModel):
    dataset: str | None
    dataset_version: str | None
    source_page: str | None = None
    download_url: str | None = None
    license: str | None = None
    synthetic: bool | None = None
    #: DATA.md §8 distinction, taken from provenance when available.
    source_dataset: SourceDataset | None = None
    canonical_graph: CanonicalGraph | None = None
    #: True when the recorded canonical counts equal the normalized tables inspected here.
    canonical_graph_consistent: bool | None = None
    neurons: int
    directed_connections: int
    self_loops: int
    synapse_count: SynapseCountStats
    missing_ids: DanglingSummary
    duplicates: DuplicateSummary
    annotation_columns: list[AnnotationColumn]

    def _source_dataset_lines(self) -> list[str]:
        source = self.source_dataset
        if source is None:
            return ["- not recorded (no provenance available)"]
        lines = [f"- name / version: {source.name} {source.version}"]
        if source.official_neuron_count is not None:
            lines.append(f"- official neuron count (approx.): {source.official_neuron_count:,}")
            if source.official_neuron_count_source:
                lines.append(f"  - basis: {source.official_neuron_count_source}")
        if source.annotated_bodies_total is not None:
            lines.append(f"- annotated bodies in release table: {source.annotated_bodies_total:,}")
        if source.raw_connection_rows is not None:
            lines.append(f"- raw connection rows: {source.raw_connection_rows:,}")
        if source.status_counts:
            counts = " · ".join(f"{k} {v:,}" for k, v in source.status_counts.items())
            lines.append(f"- status counts: {counts}")
        return lines

    def _canonical_graph_lines(self) -> list[str]:
        graph = self.canonical_graph
        if graph is None:
            return ["- not recorded (no provenance available)"]
        lines = [
            f"- selection rule: `{graph.selection_rule}`",
            f"- neurons: {graph.neuron_count:,} (subset of the source dataset, "
            "NOT its complete neuron census)",
            f"- directed connections: {graph.connection_count:,}",
        ]
        if graph.dropped_dangling_edges is not None:
            lines.append(f"- dropped dangling edges: {graph.dropped_dangling_edges:,}")
        if graph.includes_dangling_edges:
            lines.append("- includes dangling edges: yes")
        lines.append(f"- consistent with the normalized tables: {self.canonical_graph_consistent}")
        return lines

    def to_markdown(self) -> str:
        lines = [
            "# Dataset inspection report",
            "",
            f"- dataset / version: `{self.dataset}` / `{self.dataset_version}`",
            f"- source page: {self.source_page or 'n/a'}",
            f"- download url: {self.download_url or 'n/a'}",
            f"- license: {self.license or 'n/a'}",
            f"- synthetic fixture: {self.synthetic}",
            "",
            "## Source dataset",
            *self._source_dataset_lines(),
            "",
            "## Canonical simulation graph",
            *self._canonical_graph_lines(),
            "",
            "## Normalized tables",
            f"- canonical graph neurons: {self.neurons:,}",
            f"- directed connections: {self.directed_connections:,} "
            f"(self-loops: {self.self_loops:,})",
            f"- synapse_count min/max/median: {self.synapse_count.min} / "
            f"{self.synapse_count.max} / {self.synapse_count.median} "
            f"(total {self.synapse_count.total:,})",
            f"- missing IDs (dangling edges): pre {self.missing_ids.pre_missing:,}, post "
            f"{self.missing_ids.post_missing:,}, either {self.missing_ids.either_missing:,}"
            + (
                f"; sample {self.missing_ids.sample_missing_ids}"
                if self.missing_ids.sample_missing_ids
                else ""
            ),
            f"- duplicate neuron IDs: {self.duplicates.duplicate_neuron_ids:,} "
            f"({self.duplicates.duplicate_neuron_rows:,} rows)"
            + (
                f"; sample {self.duplicates.sample_duplicate_neuron_ids}"
                if self.duplicates.sample_duplicate_neuron_ids
                else ""
            ),
            f"- duplicate (pre, post) edge pairs: {self.duplicates.duplicate_edge_pairs:,}",
            "",
            "## Available annotation columns (non-null / distinct)",
        ]
        for column in self.annotation_columns:
            distinct = "-" if column.distinct is None else f"{column.distinct:,}"
            lines.append(f"- `{column.name}`: {column.non_null:,} / {distinct}")
        return "\n".join(lines) + "\n"


def _first_or_none(table: pa.Table, column: str) -> str | None:
    if column not in table.column_names or table.num_rows == 0:
        return None
    return table.column(column)[0].as_py()


def _distinct_or_none(column: pa.ChunkedArray) -> int | None:
    try:
        return pc.count_distinct(column).as_py()
    except (pa.ArrowNotImplementedError, pa.ArrowInvalid):
        return None


def inspect_tables(
    neurons: pa.Table,
    connections: pa.Table,
    *,
    provenance: dict[str, Any] | None = None,
) -> InspectionReport:
    """Compute the DATA.md §7 report for normalized tables (pure function)."""
    provenance = provenance or {}
    ids = neurons["neuron_id"]
    known = pa.array(pc.unique(ids))

    # duplicates
    id_counts = pc.value_counts(ids)
    dup_mask = pc.greater(id_counts.field("counts"), 1)
    dup_values = id_counts.field("values").filter(dup_mask)
    dup_rows = pc.sum(id_counts.field("counts").filter(dup_mask)).as_py() or 0
    pair_keys = pc.binary_join_element_wise(
        connections["pre_neuron_id"], connections["post_neuron_id"], "->"
    )
    pair_counts = pc.value_counts(pair_keys)
    duplicate_pairs = pc.sum(pc.greater(pair_counts.field("counts"), 1)).as_py() or 0

    # dangling
    pre_known = pc.is_in(connections["pre_neuron_id"], value_set=known)
    post_known = pc.is_in(connections["post_neuron_id"], value_set=known)
    pre_missing = pc.sum(pc.invert(pre_known)).as_py() or 0
    post_missing = pc.sum(pc.invert(post_known)).as_py() or 0
    either_missing = pc.sum(pc.or_(pc.invert(pre_known), pc.invert(post_known))).as_py() or 0
    missing_ids = pa.concat_arrays(
        [
            pa.array(connections["pre_neuron_id"].filter(pc.invert(pre_known))),
            pa.array(connections["post_neuron_id"].filter(pc.invert(post_known))),
        ]
    )
    sample_missing = pc.unique(missing_ids).slice(0, SAMPLE_LIMIT).to_pylist()

    counts = connections["synapse_count"]
    if connections.num_rows:
        stats = SynapseCountStats(
            min=pc.min(counts).as_py(),
            max=pc.max(counts).as_py(),
            median=float(pc.quantile(counts, q=0.5, interpolation="linear")[0].as_py()),
            total=pc.sum(counts).as_py(),
        )
        self_loops = (
            pc.sum(pc.equal(connections["pre_neuron_id"], connections["post_neuron_id"])).as_py()
            or 0
        )
    else:
        stats = SynapseCountStats(min=None, max=None, median=None, total=0)
        self_loops = 0

    annotation_columns = [
        AnnotationColumn(
            name=name,
            non_null=neurons.num_rows - neurons.column(name).null_count,
            distinct=_distinct_or_none(neurons.column(name)),
        )
        for name in neurons.column_names
        if name not in NEURON_REQUIRED_COLUMNS
    ]

    source_raw = provenance.get("source_dataset")
    canonical_raw = provenance.get("canonical_graph")
    source_dataset = (
        SourceDataset.model_validate(source_raw) if isinstance(source_raw, dict) else source_raw
    )
    canonical_graph = (
        CanonicalGraph.model_validate(canonical_raw)
        if isinstance(canonical_raw, dict)
        else canonical_raw
    )
    consistent = None
    if canonical_graph is not None:
        consistent = (
            canonical_graph.neuron_count == neurons.num_rows
            and canonical_graph.connection_count == connections.num_rows
        )

    return InspectionReport(
        dataset=provenance.get("dataset_name") or _first_or_none(neurons, "dataset"),
        dataset_version=provenance.get("dataset_version")
        or _first_or_none(neurons, "dataset_version"),
        source_page=provenance.get("source_page"),
        download_url=provenance.get("download_url"),
        license=provenance.get("license"),
        synthetic=provenance.get("synthetic"),
        source_dataset=source_dataset,
        canonical_graph=canonical_graph,
        canonical_graph_consistent=consistent,
        neurons=neurons.num_rows,
        directed_connections=connections.num_rows,
        self_loops=self_loops,
        synapse_count=stats,
        missing_ids=DanglingSummary(
            pre_missing=pre_missing,
            post_missing=post_missing,
            either_missing=either_missing,
            sample_missing_ids=[str(value) for value in sample_missing],
        ),
        duplicates=DuplicateSummary(
            duplicate_neuron_ids=len(dup_values),
            duplicate_neuron_rows=dup_rows,
            sample_duplicate_neuron_ids=[
                str(v) for v in dup_values.slice(0, SAMPLE_LIMIT).to_pylist()
            ],
            duplicate_edge_pairs=duplicate_pairs,
        ),
        annotation_columns=annotation_columns,
    )
