"""Data validation report (DATA.md §7) computed over normalized tables."""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
from pydantic import BaseModel, Field

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
    neurons: int
    directed_connections: int
    self_loops: int
    synapse_count: SynapseCountStats
    missing_ids: DanglingSummary
    duplicates: DuplicateSummary
    annotation_columns: list[AnnotationColumn]

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
            f"- neurons: {self.neurons:,}",
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

    return InspectionReport(
        dataset=provenance.get("dataset_name") or _first_or_none(neurons, "dataset"),
        dataset_version=provenance.get("dataset_version")
        or _first_or_none(neurons, "dataset_version"),
        source_page=provenance.get("source_page"),
        download_url=provenance.get("download_url"),
        license=provenance.get("license"),
        synthetic=provenance.get("synthetic"),
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
