import json

import pytest

from app.connectome import SchemaValidationError, SyntheticFixtureAdapter
from app.connectome.fixture import DEFAULT_FIXTURE_PATH


def test_fixture_file_is_labelled_synthetic() -> None:
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    assert data["synthetic"] is True
    assert "SYNTHETIC" in data["notes"]
    assert all(row["neuron_id"].startswith("syn_") for row in data["neurons"])


def test_adapter_info_and_inspection() -> None:
    adapter = SyntheticFixtureAdapter()
    assert adapter.info.synthetic is True
    assert adapter.info.dataset == "synthetic_tiny_connectome"
    assert adapter.info.source_page is None and adapter.info.download_url is None
    inspection = adapter.inspect()
    assert inspection.raw_files[0].role == "fixture"
    assert len(inspection.raw_files[0].sha256) == 64
    assert inspection.details == {"neurons": 8, "connections": 13, "synthetic_marker": "SYNTHETIC"}


def test_load_neurons_marks_every_row_synthetic() -> None:
    neurons = SyntheticFixtureAdapter().load_neurons()
    assert neurons.num_rows == 8
    assert neurons["synthetic"].to_pylist() == [True] * 8
    assert neurons["dataset"].to_pylist() == ["synthetic_tiny_connectome"] * 8
    assert neurons["region"].null_count == 8
    assert neurons["source_url"].null_count == 8
    assert neurons["cell_type"].to_pylist()[0] == "SYN_input_A"


def test_load_connections_reports_dangling_edges() -> None:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"])
    assert result.dangling is not None
    assert result.dangling.total_edges_raw == 13
    assert result.dangling.dangling_edges == 2
    assert result.table.num_rows == 11
    unknown = {"syn_unknown_1", "syn_unknown_2"}
    assert not unknown & set(result.table["post_neuron_id"].to_pylist())
    assert not unknown & set(result.table["pre_neuron_id"].to_pylist())


def test_load_connections_without_neuron_ids_returns_everything() -> None:
    result = SyntheticFixtureAdapter().load_connections()
    assert result.dangling is None and result.table.num_rows == 13


def test_validate_schema_rejects_non_synthetic_fixture(tmp_path) -> None:
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    data["synthetic"] = False
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SchemaValidationError, match="synthetic"):
        SyntheticFixtureAdapter(path).validate_schema()


def test_validate_schema_rejects_missing_keys(tmp_path) -> None:
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    del data["connections"][0]["synapse_count"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SchemaValidationError, match="synapse_count"):
        SyntheticFixtureAdapter(path).load_connections()


def test_missing_fixture_file_fails_loudly(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        SyntheticFixtureAdapter(tmp_path / "nope.json")
