"""Pure transformations from raw adapter output to the normalized data model.

These functions never invent biological fields: every optional SDD column defaults to
null unless the adapter supplies a value that exists in the source data.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.connectome.schema import (
    NEURON_OPTIONAL_COLUMNS,
    connections_schema,
    neurons_schema,
    validate_connections_table,
    validate_neurons_table,
)


@dataclass(frozen=True)
class DanglingReport:
    """How many raw edges referenced identifiers outside the neuron set."""

    total_edges_raw: int
    kept_edges: int
    pre_unknown_only: int
    post_unknown_only: int
    both_unknown: int
    kept_dangling: bool

    @property
    def dangling_edges(self) -> int:
        return self.pre_unknown_only + self.post_unknown_only + self.both_unknown

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dangling_edges"] = self.dangling_edges
        return data


def ids_to_strings(values: pa.Array | pa.ChunkedArray) -> pa.Array | pa.ChunkedArray:
    """Normalize identifiers to strings (DATA.md §5)."""
    if pa.types.is_string(values.type):
        return values
    return pc.cast(values, pa.string())


def constant_column(value: str | None, length: int) -> pa.Array:
    if value is None:
        return pa.nulls(length, pa.string())
    return pa.array([value] * length, pa.string())


def build_neurons_table(
    neuron_id: pa.Array | pa.ChunkedArray,
    *,
    dataset: str,
    dataset_version: str,
    optional: Mapping[str, pa.Array | pa.ChunkedArray | str | None] | None = None,
    extra_columns: Mapping[str, pa.Array | pa.ChunkedArray] | None = None,
) -> pa.Table:
    """Assemble a normalized neurons table.

    ``optional`` maps SDD optional column names to arrays or to a constant string; any
    omitted optional column is emitted as nulls. ``extra_columns`` are dataset-specific
    pass-through columns appended after the SDD columns.
    """
    ids = ids_to_strings(neuron_id)
    n = len(ids)
    optional = dict(optional or {})
    unknown = set(optional) - set(NEURON_OPTIONAL_COLUMNS)
    if unknown:
        raise ValueError(f"unknown optional neuron column(s): {sorted(unknown)}")

    columns: dict[str, pa.Array | pa.ChunkedArray] = {
        "neuron_id": ids,
        "dataset": constant_column(dataset, n),
        "dataset_version": constant_column(dataset_version, n),
    }
    for name in NEURON_OPTIONAL_COLUMNS:
        value = optional.get(name)
        if value is None or isinstance(value, str):
            columns[name] = constant_column(value, n)
        else:
            columns[name] = (
                pc.cast(value, pa.string()) if not pa.types.is_string(value.type) else value
            )

    extra_fields: list[pa.Field] = []
    for name, array in (extra_columns or {}).items():
        if name in columns:
            raise ValueError(f"extra column {name!r} collides with a normalized column")
        columns[name] = array
        extra_fields.append(pa.field(name, array.type))

    table = pa.table(columns).cast(neurons_schema(extra_fields))
    validate_neurons_table(table)
    return table


def build_connections_table(
    pre_neuron_id: pa.Array | pa.ChunkedArray,
    post_neuron_id: pa.Array | pa.ChunkedArray,
    synapse_count: pa.Array | pa.ChunkedArray,
    *,
    dataset: str,
    dataset_version: str,
) -> pa.Table:
    pre = ids_to_strings(pre_neuron_id)
    post = ids_to_strings(post_neuron_id)
    n = len(pre)
    table = pa.table(
        {
            "pre_neuron_id": pre,
            "post_neuron_id": post,
            "synapse_count": pc.cast(synapse_count, pa.int64()),
            "dataset": constant_column(dataset, n),
            "dataset_version": constant_column(dataset_version, n),
        }
    ).cast(connections_schema())
    validate_connections_table(table)
    return table


def classify_edges(
    pre: pa.Array | pa.ChunkedArray,
    post: pa.Array | pa.ChunkedArray,
    known_ids: pa.Array,
) -> tuple[pa.Array | pa.ChunkedArray, dict[str, int]]:
    """Return a boolean mask of edges whose endpoints are both known, plus counts."""
    pre_known = pc.is_in(pre, value_set=known_ids)
    post_known = pc.is_in(post, value_set=known_ids)
    both = pc.and_(pre_known, post_known)
    counts = {
        "kept": pc.sum(both).as_py() or 0,
        "pre_unknown_only": pc.sum(pc.and_(pc.invert(pre_known), post_known)).as_py() or 0,
        "post_unknown_only": pc.sum(pc.and_(pre_known, pc.invert(post_known))).as_py() or 0,
        "both_unknown": pc.sum(pc.and_(pc.invert(pre_known), pc.invert(post_known))).as_py() or 0,
    }
    return both, counts


def filter_dangling(
    connections: pa.Table,
    neuron_ids: pa.Array | pa.ChunkedArray,
    *,
    keep_dangling: bool = False,
) -> tuple[pa.Table, DanglingReport]:
    """Drop (or keep, but report) edges that reference identifiers absent from ``neuron_ids``."""
    known = pa.array(pc.unique(ids_to_strings(neuron_ids)))
    mask, counts = classify_edges(
        connections["pre_neuron_id"], connections["post_neuron_id"], known
    )
    report = DanglingReport(
        total_edges_raw=connections.num_rows,
        kept_edges=connections.num_rows if keep_dangling else counts["kept"],
        pre_unknown_only=counts["pre_unknown_only"],
        post_unknown_only=counts["post_unknown_only"],
        both_unknown=counts["both_unknown"],
        kept_dangling=keep_dangling,
    )
    if keep_dangling:
        return connections, report
    return connections.filter(mask), report


def write_parquet(table: pa.Table, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd")
    return path


def read_parquet(path: Path) -> pa.Table:
    return pq.read_table(path)


def sha256_file(path: Path, chunk_size: int = 1 << 24) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path, chunk_size: int = 1 << 24) -> str:
    digest = hashlib.md5()  # noqa: S324 - integrity check against the publisher's md5, not security
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
