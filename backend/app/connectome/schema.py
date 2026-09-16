"""Normalized data model (SDD §3) as pyarrow schemas plus fail-loud validation.

BIOLOGICAL STRUCTURE layer. Only structure is described here; nothing is inferred about
biology. Identifiers are strings (DATA.md §5). Unknown optional fields are null.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pyarrow as pa
import pyarrow.compute as pc

#: Required columns of ``neurons.parquet`` (SDD §3).
NEURON_REQUIRED_COLUMNS: tuple[str, ...] = ("neuron_id", "dataset", "dataset_version")

#: Optional, nullable columns of ``neurons.parquet`` (SDD §3).
NEURON_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "cell_type",
    "cell_class",
    "region",
    "neurotransmitter",
    "sex",
    "source_url",
)

#: Columns of ``connections.parquet`` (SDD §3).
CONNECTION_COLUMNS: tuple[str, ...] = (
    "pre_neuron_id",
    "post_neuron_id",
    "synapse_count",
    "dataset",
    "dataset_version",
)

#: Prefix used for dataset-specific columns preserved verbatim next to the SDD columns.
RAW_PASSTHROUGH_PREFIX = "mcns_"


class SchemaValidationError(ValueError):
    """Raised when a table does not satisfy the normalized data model."""


def neurons_schema(extra_fields: Sequence[pa.Field] = ()) -> pa.Schema:
    """Schema of ``neurons.parquet``: SDD columns first, then any dataset-specific extras."""
    fields = [
        pa.field("neuron_id", pa.string(), nullable=False),
        pa.field("dataset", pa.string(), nullable=False),
        pa.field("dataset_version", pa.string(), nullable=False),
        pa.field("cell_type", pa.string()),
        pa.field("cell_class", pa.string()),
        pa.field("region", pa.string()),
        pa.field("neurotransmitter", pa.string()),
        pa.field("sex", pa.string()),
        pa.field("source_url", pa.string()),
    ]
    fields.extend(extra_fields)
    return pa.schema(fields)


def connections_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("pre_neuron_id", pa.string(), nullable=False),
            pa.field("post_neuron_id", pa.string(), nullable=False),
            pa.field("synapse_count", pa.int64(), nullable=False),
            pa.field("dataset", pa.string(), nullable=False),
            pa.field("dataset_version", pa.string(), nullable=False),
        ]
    )


def _require_columns(table: pa.Table, required: Iterable[str], what: str) -> None:
    missing = [name for name in required if name not in table.column_names]
    if missing:
        raise SchemaValidationError(f"{what}: missing required column(s) {missing}")


def _require_string_non_null(table: pa.Table, column: str, what: str) -> None:
    col = table.column(column)
    if not pa.types.is_string(col.type) and not pa.types.is_large_string(col.type):
        raise SchemaValidationError(f"{what}: column {column!r} must be string, got {col.type}")
    if col.null_count:
        raise SchemaValidationError(f"{what}: column {column!r} has {col.null_count} null value(s)")


def validate_neurons_table(table: pa.Table) -> None:
    """Fail loudly unless ``table`` is a valid normalized neurons table."""
    what = "neurons"
    _require_columns(table, NEURON_REQUIRED_COLUMNS, what)
    for column in NEURON_REQUIRED_COLUMNS:
        _require_string_non_null(table, column, what)
    for column in NEURON_OPTIONAL_COLUMNS:
        if column in table.column_names:
            col_type = table.column(column).type
            if not (
                pa.types.is_string(col_type)
                or pa.types.is_large_string(col_type)
                or pa.types.is_null(col_type)
            ):
                raise SchemaValidationError(
                    f"{what}: optional column {column!r} must be string/null, got {col_type}"
                )


def validate_connections_table(table: pa.Table) -> None:
    """Fail loudly unless ``table`` is a valid normalized connections table."""
    what = "connections"
    _require_columns(table, CONNECTION_COLUMNS, what)
    for column in ("pre_neuron_id", "post_neuron_id", "dataset", "dataset_version"):
        _require_string_non_null(table, column, what)
    counts = table.column("synapse_count")
    if not pa.types.is_integer(counts.type):
        raise SchemaValidationError(f"{what}: 'synapse_count' must be integer, got {counts.type}")
    if counts.null_count:
        raise SchemaValidationError(
            f"{what}: 'synapse_count' has {counts.null_count} null value(s)"
        )
    if table.num_rows and pc.min(counts).as_py() < 0:
        raise SchemaValidationError(f"{what}: 'synapse_count' contains negative values")
