import pyarrow as pa

from app.connectome import SyntheticFixtureAdapter, inspect_tables
from app.connectome.normalize import build_connections_table, build_neurons_table


def test_fixture_report_matches_known_numbers() -> None:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"], keep_dangling=True)
    report = inspect_tables(
        neurons,
        result.table,
        provenance={"dataset_name": "x", "dataset_version": "y", "synthetic": True},
    )
    assert report.dataset == "x" and report.dataset_version == "y" and report.synthetic is True
    assert report.neurons == 8
    assert report.directed_connections == 13
    assert report.self_loops == 1
    assert report.synapse_count.min == 1 and report.synapse_count.max == 20
    assert report.synapse_count.median == 5.0
    assert report.synapse_count.total == 86
    assert report.missing_ids.pre_missing == 1 and report.missing_ids.post_missing == 1
    assert report.missing_ids.either_missing == 2
    assert set(report.missing_ids.sample_missing_ids) == {"syn_unknown_1", "syn_unknown_2"}
    assert (
        report.duplicates.duplicate_neuron_ids == 0 and report.duplicates.duplicate_edge_pairs == 0
    )
    names = {column.name for column in report.annotation_columns}
    assert {"cell_type", "cell_class", "region", "synthetic"} <= names
    cell_type = next(c for c in report.annotation_columns if c.name == "cell_type")
    assert cell_type.non_null == 7 and cell_type.distinct == 7


def test_report_after_dropping_dangling_edges_is_clean() -> None:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"])
    report = inspect_tables(neurons, result.table)
    assert report.directed_connections == 11
    assert report.missing_ids.either_missing == 0
    assert report.dataset == "synthetic_tiny_connectome"  # falls back to the table's dataset column


def test_report_detects_duplicates() -> None:
    neurons = build_neurons_table(pa.array(["a", "a", "b"]), dataset="d", dataset_version="v")
    connections = build_connections_table(
        pa.array(["a", "a", "b"]),
        pa.array(["b", "b", "a"]),
        pa.array([1, 2, 3], pa.int64()),
        dataset="d",
        dataset_version="v",
    )
    report = inspect_tables(neurons, connections)
    assert report.duplicates.duplicate_neuron_ids == 1
    assert report.duplicates.duplicate_neuron_rows == 2
    assert report.duplicates.sample_duplicate_neuron_ids == ["a"]
    assert report.duplicates.duplicate_edge_pairs == 1


def test_empty_connections_do_not_crash() -> None:
    neurons = build_neurons_table(pa.array(["a"]), dataset="d", dataset_version="v")
    connections = build_connections_table(
        pa.array([], pa.string()),
        pa.array([], pa.string()),
        pa.array([], pa.int64()),
        dataset="d",
        dataset_version="v",
    )
    report = inspect_tables(neurons, connections)
    assert (
        report.directed_connections == 0
        and report.synapse_count.min is None
        and report.synapse_count.total == 0
    )
    assert "neurons: 1" in report.to_markdown()


def test_markdown_rendering_mentions_key_fields() -> None:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    report = inspect_tables(
        neurons,
        adapter.load_connections().table,
        provenance={"license": "synthetic", "synthetic": True},
    )
    text = report.to_markdown()
    assert "license: synthetic" in text and "synthetic fixture: True" in text
    assert "dangling edges" in text and "`cell_type`" in text
