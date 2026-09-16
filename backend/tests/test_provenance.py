import pytest

from app.connectome import CanonicalGraph, Provenance, RawFileEntry, SourceDataset


def test_biological_dataset_requires_license() -> None:
    with pytest.raises(ValueError, match="license"):
        Provenance(dataset_name="male-cns", dataset_version="v1.0", license="")


def test_synthetic_dataset_may_omit_license() -> None:
    provenance = Provenance(dataset_name="synthetic", dataset_version="fixture-v1", synthetic=True)
    assert provenance.license is None


def test_round_trip_through_json(tmp_path) -> None:
    provenance = Provenance(
        dataset_name="male-cns",
        dataset_version="v1.0",
        source_dataset=SourceDataset(name="MaleCNS", version="v1.0", official_neuron_count=166_700),
        canonical_graph=CanonicalGraph(
            selection_rule='status == "Traced"', neuron_count=165_122, connection_count=25_563_197
        ),
        source_page="https://male-cns.janelia.org/download/",
        download_url="gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/",
        retrieved_at="2026-09-16T12:00:00+00:00",
        license="CC-BY 4.0",
        raw_files=[
            RawFileEntry(
                role="weights",
                path="data/raw/x.feather",
                size_bytes=1,
                sha256="0" * 64,
                md5="1" * 32,
            )
        ],
        transform_script="scripts/normalize_dataset.py",
        counts={"neurons": 1},
    )
    path = provenance.write(tmp_path / "provenance.json")
    loaded = Provenance.read(path)
    assert loaded == provenance
    assert loaded.raw_files[0].md5_matches_expected is None
    text = path.read_text()
    assert '"dataset_name": "male-cns"' in text and text.endswith("\n")
