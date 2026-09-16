"""Production adapter tests using SYNTHETIC files with the verified MaleCNS v1.0 schema."""

import base64

import pyarrow as pa
import pytest

from app.connectome import MaleCnsConfig, MaleCnsV1Adapter, SchemaValidationError
from app.connectome.malecns import (
    ANNOTATION_COLUMNS,
    ANNOTATIONS_FILE,
    BUCKET_MD5_BASE64,
    WEIGHTS_FILE,
    expected_md5_hex,
    https_url,
)
from tests.synthetic_malecns import (
    EXPECTED_TRACED_EDGES,
    SYNTHETIC_BODIES,
    SYNTHETIC_EDGES,
    TRACED_IDS,
    write_synthetic_malecns_raw,
)


@pytest.fixture
def raw_dir(tmp_path):
    write_synthetic_malecns_raw(tmp_path)
    return tmp_path


def make_adapter(raw_dir, **overrides) -> MaleCnsV1Adapter:
    return MaleCnsV1Adapter(MaleCnsConfig(raw_dir=raw_dir, **overrides))


def test_dataset_info_is_the_official_male_cns_release(raw_dir) -> None:
    info = make_adapter(raw_dir).info
    assert info.dataset == "male-cns" and info.dataset_version == "v1.0"
    assert info.synthetic is False
    assert info.download_url == "gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/"
    assert info.source_page == "https://male-cns.janelia.org/download/"
    assert "CC-BY" in (info.license or "")
    assert "cell.com" in (info.citation or "")


def test_expected_md5_is_decoded_from_bucket_listing() -> None:
    for name, encoded in BUCKET_MD5_BASE64.items():
        assert expected_md5_hex(name) == base64.b64decode(encoded).hex()
    assert expected_md5_hex("unknown.feather") is None
    assert https_url(WEIGHTS_FILE).startswith("https://storage.googleapis.com/flyem-male-cns/v1.0/")


def test_validate_schema_passes_on_verified_columns(raw_dir) -> None:
    make_adapter(raw_dir).validate_schema()


def test_validate_schema_fails_when_required_column_missing(tmp_path) -> None:
    write_synthetic_malecns_raw(tmp_path, drop_annotation_columns=("status",))
    with pytest.raises(SchemaValidationError, match="status"):
        make_adapter(tmp_path).validate_schema()


def test_validate_schema_fails_when_file_missing(tmp_path) -> None:
    write_synthetic_malecns_raw(tmp_path, include_weights=False)
    with pytest.raises(FileNotFoundError, match="weights"):
        make_adapter(tmp_path).validate_schema()


def test_load_neurons_default_rule_keeps_traced_bodies_only(raw_dir) -> None:
    neurons = make_adapter(raw_dir).load_neurons()
    assert neurons["neuron_id"].to_pylist() == [str(b) for b in sorted(TRACED_IDS)]
    assert neurons["dataset"].to_pylist() == ["male-cns"] * len(TRACED_IDS)
    assert neurons["dataset_version"].to_pylist() == ["v1.0"] * len(TRACED_IDS)
    assert neurons["cell_type"].to_pylist() == [SYNTHETIC_BODIES[b][1] for b in sorted(TRACED_IDS)]
    assert neurons["cell_class"].to_pylist() == [SYNTHETIC_BODIES[b][2] for b in sorted(TRACED_IDS)]
    assert neurons["region"].null_count == neurons.num_rows  # never invented
    assert set(neurons["sex"].to_pylist()) == {"male"}
    assert set(neurons["source_url"].to_pylist()) == {https_url(ANNOTATIONS_FILE)}


def test_load_neurons_carries_raw_columns_with_prefix(raw_dir) -> None:
    neurons = make_adapter(raw_dir).load_neurons()
    for column in ANNOTATION_COLUMNS:
        if column != "bodyId":
            assert f"mcns_{column}" in neurons.column_names, column
    assert neurons["mcns_status"].to_pylist() == ["Traced"] * len(TRACED_IDS)
    assert pa.types.is_string(neurons["mcns_statusLabel"].type)  # dictionary decoded
    assert neurons["mcns_superclass"].to_pylist()[0] == "synthetic_super_1"


def test_load_neurons_joins_neurotransmitter_predictions(raw_dir) -> None:
    neurons = make_adapter(raw_dir).load_neurons()
    by_id = dict(
        zip(neurons["neuron_id"].to_pylist(), neurons["neurotransmitter"].to_pylist(), strict=True)
    )
    assert by_id["1001"] == "synthetic_nt_a"
    assert by_id["1003"] == "unclear"
    assert by_id["1004"] is None  # no prediction row for this body
    assert "mcns_nt_predicted_nt_confidence" in neurons.column_names
    assert "mcns_nt_consensus_nt" in neurons.column_names
    assert (
        "1006" not in by_id
    )  # Orphan body with a prediction is not a neuron under the default rule


def test_load_neurons_without_neurotransmitter_file(raw_dir) -> None:
    neurons = make_adapter(raw_dir, neurotransmitters_file=None).load_neurons()
    assert neurons["neurotransmitter"].null_count == neurons.num_rows
    assert not [c for c in neurons.column_names if c.startswith("mcns_nt_")]


def test_status_filter_is_configurable(raw_dir) -> None:
    assert make_adapter(raw_dir, neuron_status_filter=()).load_neurons().num_rows == len(
        SYNTHETIC_BODIES
    )
    both = make_adapter(raw_dir, neuron_status_filter=("Traced", "Assign")).load_neurons()
    assert both.num_rows == len(TRACED_IDS) + 1
    assert "1008" in both["neuron_id"].to_pylist()


def test_load_connections_filters_to_neuron_set_and_reports_dangling(raw_dir) -> None:
    adapter = make_adapter(raw_dir)
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"])
    table = result.table
    expected = sorted(EXPECTED_TRACED_EDGES)
    assert list(
        zip(table["pre_neuron_id"].to_pylist(), table["post_neuron_id"].to_pylist(), strict=True)
    ) == [(str(pre), str(post)) for pre, post, _ in expected]
    assert table["synapse_count"].to_pylist() == [w for _, _, w in expected]
    report = result.dangling
    assert report is not None
    assert report.total_edges_raw == len(SYNTHETIC_EDGES)
    assert report.kept_edges == len(EXPECTED_TRACED_EDGES)
    assert report.post_unknown_only == 1  # 1001 -> 1006 (Orphan)
    assert report.pre_unknown_only == 2  # 1007 (Glia) -> 1003, 1008 (Assign) -> 1002
    assert report.both_unknown == 1  # 1006 -> 1007
    assert report.dangling_edges == 4


def test_load_connections_can_keep_dangling_or_skip_filtering(raw_dir) -> None:
    adapter = make_adapter(raw_dir)
    neurons = adapter.load_neurons()
    kept = adapter.load_connections(neurons["neuron_id"], keep_dangling=True)
    assert kept.table.num_rows == len(SYNTHETIC_EDGES) and kept.dangling is not None
    assert kept.dangling.kept_dangling is True and kept.dangling.dangling_edges == 4
    everything = adapter.load_connections()
    assert everything.table.num_rows == len(SYNTHETIC_EDGES) and everything.dangling is None


def test_connections_are_sorted_and_stringified(raw_dir) -> None:
    table = make_adapter(raw_dir).load_connections().table
    pairs = list(
        zip(table["pre_neuron_id"].to_pylist(), table["post_neuron_id"].to_pylist(), strict=True)
    )
    assert pairs == sorted(pairs, key=lambda p: (int(p[0]), int(p[1])))
    assert pa.types.is_string(table["pre_neuron_id"].type)


def test_outputs_are_deterministic(raw_dir) -> None:
    a, b = make_adapter(raw_dir), make_adapter(raw_dir)
    assert a.load_neurons().equals(b.load_neurons())
    assert a.load_connections().table.equals(b.load_connections().table)


def test_inspect_reports_files_columns_and_checksums(raw_dir) -> None:
    inspection = make_adapter(raw_dir).inspect()
    roles = {record.role: record for record in inspection.raw_files}
    assert set(roles) == {"annotations", "weights", "neurotransmitters"}
    assert roles["annotations"].columns == ANNOTATION_COLUMNS
    assert roles["weights"].columns == ("body_pre", "body_post", "weight")
    assert len(roles["weights"].sha256) == 64 and len(roles["weights"].md5 or "") == 32
    # synthetic content can never match the published checksum -> mismatch must be visible
    assert roles["weights"].expected_md5 == expected_md5_hex(WEIGHTS_FILE)
    assert roles["weights"].md5_matches_expected is False
    assert inspection.details["column_diffs"]["annotations"] == {
        "missing_vs_verified": [],
        "unexpected_vs_verified": [],
    }
    assert inspection.details["neuron_status_filter"] == ["Traced"]
    assert inspection.details["retrieved_at"]
    assert inspection.details["missing_files"] == []


def test_inspect_lists_missing_files_and_skips_hashes_when_asked(tmp_path) -> None:
    write_synthetic_malecns_raw(tmp_path, include_neurotransmitters=False)
    inspection = make_adapter(tmp_path, compute_hashes=False).inspect()
    assert len(inspection.details["missing_files"]) == 1
    assert all(record.sha256 == "" and record.md5 is None for record in inspection.raw_files)
    assert all(record.md5_matches_expected is None for record in inspection.raw_files)
    assert {record.role for record in inspection.raw_files} == {"annotations", "weights"}
    dictified = inspection.to_dict(relative_to=tmp_path)
    assert dictified["raw_files"][0]["path"] == ANNOTATIONS_FILE
    assert dictified["info"]["synthetic"] is False


def test_neuron_ids_passed_as_ints_or_strings_behave_the_same(raw_dir) -> None:
    adapter = make_adapter(raw_dir)
    as_strings = adapter.load_connections(pa.array([str(b) for b in TRACED_IDS])).table
    as_ints = adapter.load_connections(pa.array(TRACED_IDS, pa.int64())).table
    assert as_strings.equals(as_ints)
