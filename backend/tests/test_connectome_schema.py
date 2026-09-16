import pyarrow as pa
import pytest

from app.connectome.schema import (
    CONNECTION_COLUMNS,
    NEURON_REQUIRED_COLUMNS,
    SchemaValidationError,
    connections_schema,
    neurons_schema,
    validate_connections_table,
    validate_neurons_table,
)


def _neurons(**overrides: pa.Array) -> pa.Table:
    base = {
        "neuron_id": pa.array(["a", "b"], pa.string()),
        "dataset": pa.array(["d", "d"], pa.string()),
        "dataset_version": pa.array(["v", "v"], pa.string()),
    }
    base.update(overrides)
    return pa.table(base)


def _connections(**overrides: pa.Array) -> pa.Table:
    base = {
        "pre_neuron_id": pa.array(["a"], pa.string()),
        "post_neuron_id": pa.array(["b"], pa.string()),
        "synapse_count": pa.array([3], pa.int64()),
        "dataset": pa.array(["d"], pa.string()),
        "dataset_version": pa.array(["v"], pa.string()),
    }
    base.update(overrides)
    return pa.table(base)


def test_schemas_list_sdd_columns() -> None:
    assert neurons_schema().names[:3] == list(NEURON_REQUIRED_COLUMNS)
    assert connections_schema().names == list(CONNECTION_COLUMNS)
    assert neurons_schema([pa.field("extra", pa.bool_())]).names[-1] == "extra"


def test_valid_tables_pass() -> None:
    validate_neurons_table(_neurons())
    validate_connections_table(_connections())


def test_missing_required_neuron_column_fails() -> None:
    table = _neurons().drop_columns(["dataset_version"])
    with pytest.raises(SchemaValidationError, match="dataset_version"):
        validate_neurons_table(table)


def test_integer_ids_are_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="must be string"):
        validate_neurons_table(_neurons(neuron_id=pa.array([1, 2], pa.int64())))


def test_null_ids_are_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="null"):
        validate_neurons_table(_neurons(neuron_id=pa.array(["a", None], pa.string())))


def test_optional_column_must_be_string() -> None:
    with pytest.raises(SchemaValidationError, match="cell_type"):
        validate_neurons_table(_neurons(cell_type=pa.array([1, 2], pa.int64())))


def test_connections_require_integer_non_negative_counts() -> None:
    with pytest.raises(SchemaValidationError, match="integer"):
        validate_connections_table(_connections(synapse_count=pa.array([1.5], pa.float64())))
    with pytest.raises(SchemaValidationError, match="negative"):
        validate_connections_table(_connections(synapse_count=pa.array([-1], pa.int64())))
    with pytest.raises(SchemaValidationError, match="null"):
        validate_connections_table(_connections(synapse_count=pa.array([None], pa.int64())))


def test_connections_missing_column_fails() -> None:
    with pytest.raises(SchemaValidationError, match="post_neuron_id"):
        validate_connections_table(_connections().drop_columns(["post_neuron_id"]))
