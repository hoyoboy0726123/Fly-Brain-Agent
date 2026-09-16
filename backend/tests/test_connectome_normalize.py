import pyarrow as pa
import pytest

from app.connectome.normalize import (
    build_connections_table,
    build_neurons_table,
    classify_edges,
    filter_dangling,
    ids_to_strings,
    read_parquet,
    write_parquet,
)


def test_ids_to_strings_casts_integers_and_keeps_strings() -> None:
    assert ids_to_strings(pa.array([10001, 7], pa.int64())).to_pylist() == ["10001", "7"]
    assert ids_to_strings(pa.array(["x"], pa.string())).to_pylist() == ["x"]


def test_build_neurons_table_defaults_optional_columns_to_null() -> None:
    table = build_neurons_table(pa.array([3, 1], pa.int64()), dataset="d", dataset_version="v")
    assert table.column_names[:3] == ["neuron_id", "dataset", "dataset_version"]
    assert table["neuron_id"].to_pylist() == ["3", "1"]
    for column in ("cell_type", "cell_class", "region", "neurotransmitter", "sex", "source_url"):
        assert table[column].null_count == 2, column


def test_build_neurons_table_accepts_constants_arrays_and_extras() -> None:
    table = build_neurons_table(
        pa.array(["a", "b"]),
        dataset="d",
        dataset_version="v",
        optional={"sex": "male", "cell_type": pa.array(["T1", None])},
        extra_columns={"mcns_status": pa.array(["Traced", "Orphan"])},
    )
    assert table["sex"].to_pylist() == ["male", "male"]
    assert table["cell_type"].to_pylist() == ["T1", None]
    assert table["mcns_status"].to_pylist() == ["Traced", "Orphan"]


def test_build_neurons_table_rejects_unknown_optional_and_collisions() -> None:
    with pytest.raises(ValueError, match="unknown optional"):
        build_neurons_table(
            pa.array(["a"]), dataset="d", dataset_version="v", optional={"bogus": "x"}
        )
    with pytest.raises(ValueError, match="collides"):
        build_neurons_table(
            pa.array(["a"]),
            dataset="d",
            dataset_version="v",
            extra_columns={"neuron_id": pa.array(["z"])},
        )


def test_build_connections_table_casts_ids_and_counts() -> None:
    table = build_connections_table(
        pa.array([1, 2], pa.int64()),
        pa.array([2, 3], pa.int64()),
        pa.array([5, 6], pa.int32()),
        dataset="d",
        dataset_version="v",
    )
    assert table["pre_neuron_id"].to_pylist() == ["1", "2"]
    assert table["synapse_count"].type == pa.int64()
    assert table["dataset"].to_pylist() == ["d", "d"]


def test_classify_edges_counts_each_category() -> None:
    known = pa.array(["a", "b"])
    pre = pa.array(["a", "x", "a", "x"])
    post = pa.array(["b", "b", "y", "y"])
    mask, counts = classify_edges(pre, post, known)
    assert mask.to_pylist() == [True, False, False, False]
    assert counts == {"kept": 1, "pre_unknown_only": 1, "post_unknown_only": 1, "both_unknown": 1}


def _edges() -> pa.Table:
    return build_connections_table(
        pa.array(["a", "a", "z", "b"]),
        pa.array(["b", "q", "a", "b"]),
        pa.array([1, 2, 3, 4], pa.int64()),
        dataset="d",
        dataset_version="v",
    )


def test_filter_dangling_drops_and_reports() -> None:
    kept, report = filter_dangling(_edges(), pa.array(["a", "b"]))
    assert kept.num_rows == 2
    assert kept["pre_neuron_id"].to_pylist() == ["a", "b"]
    assert report.total_edges_raw == 4 and report.kept_edges == 2
    assert (
        report.post_unknown_only == 1 and report.pre_unknown_only == 1 and report.both_unknown == 0
    )
    assert report.dangling_edges == 2 and report.kept_dangling is False
    assert report.to_dict()["dangling_edges"] == 2


def test_filter_dangling_can_keep_edges_but_still_reports() -> None:
    kept, report = filter_dangling(_edges(), pa.array(["a", "b"]), keep_dangling=True)
    assert kept.num_rows == 4
    assert report.kept_edges == 4 and report.dangling_edges == 2 and report.kept_dangling is True


def test_parquet_round_trip(tmp_path) -> None:
    table = _edges()
    path = write_parquet(table, tmp_path / "nested" / "connections.parquet")
    assert path.is_file()
    assert read_parquet(path).equals(table)
