"""P1.1 guards: the SOURCE DATASET and the CANONICAL SIMULATION GRAPH stay distinct (DATA.md §8)."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.connectome import (
    CanonicalGraph,
    MaleCnsConfig,
    MaleCnsV1Adapter,
    Provenance,
    SourceDataset,
    SyntheticFixtureAdapter,
    inspect_tables,
)
from app.connectome.malecns import (
    DEFAULT_STATUS_FILTER,
    OFFICIAL_NEURON_COUNT,
    SOURCE_NAME,
)
from tests.synthetic_malecns import (
    EXPECTED_TRACED_EDGES,
    SYNTHETIC_BODIES,
    SYNTHETIC_EDGES,
    TRACED_IDS,
    write_synthetic_malecns_raw,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT_ROOT / "data" / "processed"
SCRIPTS = PROJECT_ROOT / "scripts"

CANONICAL_RULE = 'status == "Traced"'
CANONICAL_NEURONS = 165_122
CANONICAL_CONNECTIONS = 25_563_197
SOURCE_OFFICIAL_NEURONS = 166_700


# ----------------------------------------------------------------- behaviour is unchanged
def test_default_selection_rule_is_still_traced() -> None:
    assert DEFAULT_STATUS_FILTER == ("Traced",)
    assert MaleCnsConfig(raw_dir=Path(".")).selection_rule == CANONICAL_RULE


def test_selection_rule_rendering() -> None:
    assert MaleCnsConfig(raw_dir=Path("."), neuron_status_filter=()).selection_rule == (
        "all annotated bodies (no status filter)"
    )
    assert (
        MaleCnsConfig(raw_dir=Path("."), neuron_status_filter=("Traced", "Assign")).selection_rule
        == 'status in ["Traced", "Assign"]'
    )


def test_adapter_reports_source_dataset_count_separately(tmp_path) -> None:
    write_synthetic_malecns_raw(tmp_path)
    adapter = MaleCnsV1Adapter(MaleCnsConfig(raw_dir=tmp_path, compute_hashes=False))
    assert adapter.info.source_name == SOURCE_NAME == "MaleCNS"
    assert adapter.info.official_neuron_count == OFFICIAL_NEURON_COUNT == SOURCE_OFFICIAL_NEURONS
    assert "Not the canonical graph count" in (adapter.info.official_neuron_count_source or "")
    details = adapter.inspect().details
    assert details["selection_rule"] == CANONICAL_RULE
    assert details["annotated_bodies_total"] == len(SYNTHETIC_BODIES)
    assert details["status_counts"]["Traced"] == len(TRACED_IDS)
    assert details["raw_connection_rows"] == len(SYNTHETIC_EDGES)
    assert details["bodies_with_superclass"] == sum(
        1 for row in SYNTHETIC_BODIES.values() if row[3]
    )
    # the canonical graph is the Traced subset, smaller than the annotated total
    assert adapter.load_neurons().num_rows == len(TRACED_IDS) < details["annotated_bodies_total"]


# -------------------------------------------------------------------------- provenance
def _source() -> SourceDataset:
    return SourceDataset(
        name="MaleCNS", version="v1.0", official_neuron_count=SOURCE_OFFICIAL_NEURONS
    )


def _canonical() -> CanonicalGraph:
    return CanonicalGraph(
        selection_rule=CANONICAL_RULE,
        neuron_count=CANONICAL_NEURONS,
        connection_count=CANONICAL_CONNECTIONS,
    )


def test_biological_provenance_requires_both_blocks() -> None:
    with pytest.raises(ValueError, match="source_dataset and canonical_graph"):
        Provenance(dataset_name="male-cns", dataset_version="v1.0", license="CC-BY")
    with pytest.raises(ValueError, match="source_dataset and canonical_graph"):
        Provenance(
            dataset_name="male-cns",
            dataset_version="v1.0",
            license="CC-BY",
            source_dataset=_source(),
        )
    Provenance(
        dataset_name="male-cns",
        dataset_version="v1.0",
        license="CC-BY",
        source_dataset=_source(),
        canonical_graph=_canonical(),
    )


def test_canonical_graph_requires_a_selection_rule() -> None:
    with pytest.raises(ValueError):
        CanonicalGraph(selection_rule="", neuron_count=1, connection_count=1)


def test_synthetic_provenance_may_omit_blocks() -> None:
    assert Provenance(dataset_name="s", dataset_version="f", synthetic=True).canonical_graph is None


# ------------------------------------------------------------- committed production artefacts
@pytest.fixture(scope="module")
def committed_provenance() -> Provenance:
    path = PROCESSED / "provenance.json"
    if not path.is_file():
        pytest.skip("data/processed/provenance.json not present")
    return Provenance.read(path)


def test_committed_provenance_distinguishes_source_and_canonical(
    committed_provenance: Provenance,
) -> None:
    source = committed_provenance.source_dataset
    graph = committed_provenance.canonical_graph
    assert source is not None and graph is not None
    assert source.name == "MaleCNS" and source.version == "v1.0"
    assert source.official_neuron_count == SOURCE_OFFICIAL_NEURONS
    assert source.annotated_bodies_total == 211_577
    assert source.status_counts["Traced"] == CANONICAL_NEURONS
    assert source.raw_connection_rows == 151_856_684
    assert graph.selection_rule == CANONICAL_RULE
    assert graph.neuron_count == CANONICAL_NEURONS
    assert graph.connection_count == CANONICAL_CONNECTIONS
    assert graph.dropped_dangling_edges == 126_293_487
    assert graph.includes_dangling_edges is False
    assert graph.neuron_count != source.official_neuron_count
    assert committed_provenance.counts["neurons"] == graph.neuron_count
    assert committed_provenance.counts["connections"] == graph.connection_count


def test_committed_inspection_report_matches_provenance(committed_provenance: Provenance) -> None:
    report = json.loads((PROCESSED / "inspection_report.json").read_text())
    assert report["neurons"] == committed_provenance.canonical_graph.neuron_count
    assert report["directed_connections"] == committed_provenance.canonical_graph.connection_count
    assert report["canonical_graph"]["selection_rule"] == CANONICAL_RULE
    assert report["source_dataset"]["official_neuron_count"] == SOURCE_OFFICIAL_NEURONS
    assert report["canonical_graph_consistent"] is True
    markdown = (PROCESSED / "inspection_report.md").read_text()
    assert "## Source dataset" in markdown and "## Canonical simulation graph" in markdown
    assert "NOT its complete neuron census" in markdown


# ------------------------------------------------------------------- inspection report
def test_inspect_report_prints_both_sections_and_checks_consistency() -> None:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"])
    provenance = {
        "source_dataset": SourceDataset(
            name="synthetic", version="f", official_neuron_count=8
        ).model_dump(),
        "canonical_graph": CanonicalGraph(
            selection_rule="all", neuron_count=8, connection_count=11
        ).model_dump(),
    }
    report = inspect_tables(neurons, result.table, provenance=provenance)
    assert report.canonical_graph_consistent is True
    text = report.to_markdown()
    assert "## Source dataset" in text and "## Canonical simulation graph" in text
    assert "official neuron count (approx.): 8" in text
    assert "selection rule: `all`" in text
    stale = dict(provenance)
    stale["canonical_graph"] = CanonicalGraph(
        selection_rule="all", neuron_count=7, connection_count=11
    ).model_dump()
    assert (
        inspect_tables(neurons, result.table, provenance=stale).canonical_graph_consistent is False
    )
    without = inspect_tables(neurons, result.table)
    assert without.canonical_graph_consistent is None
    assert "not recorded" in without.to_markdown()


# ------------------------------------------------------------------------- CLI scripts
def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def test_normalize_script_records_both_blocks(tmp_path) -> None:
    raw, out = tmp_path / "raw", tmp_path / "out"
    write_synthetic_malecns_raw(raw)
    result = run(
        str(SCRIPTS / "normalize_dataset.py"),
        "--adapter",
        "malecns",
        "--raw-dir",
        str(raw),
        "--out-dir",
        str(out),
        "--no-hash",
    )
    assert result.returncode == 0, result.stderr
    assert "SOURCE DATASET MaleCNS v1.0" in result.stdout and "CANONICAL GRAPH" in result.stdout
    provenance = Provenance.read(out / "provenance.json")
    assert provenance.source_dataset is not None and provenance.canonical_graph is not None
    assert provenance.source_dataset.official_neuron_count == SOURCE_OFFICIAL_NEURONS
    assert provenance.source_dataset.annotated_bodies_total == len(SYNTHETIC_BODIES)
    assert provenance.source_dataset.raw_connection_rows == len(SYNTHETIC_EDGES)
    assert provenance.canonical_graph.selection_rule == CANONICAL_RULE
    assert provenance.canonical_graph.neuron_count == len(TRACED_IDS)
    assert provenance.canonical_graph.connection_count == len(EXPECTED_TRACED_EDGES)
    assert provenance.canonical_graph.dropped_dangling_edges == len(SYNTHETIC_EDGES) - len(
        EXPECTED_TRACED_EDGES
    )

    import pyarrow.parquet as pq

    metadata = pq.read_schema(out / "neurons.parquet").metadata
    assert metadata[b"flybrain.canonical_graph.selection_rule"].decode() == CANONICAL_RULE
    assert metadata[b"flybrain.source_dataset"].decode() == "MaleCNS v1.0"

    report = json.loads((out / "inspection_report.json").read_text())
    assert report["canonical_graph_consistent"] is True


def test_inspect_fixture_prints_both_sections() -> None:
    result = run(str(SCRIPTS / "inspect_dataset.py"), "--fixture")
    assert result.returncode == 0, result.stderr
    assert "## Source dataset" in result.stdout and "## Canonical simulation graph" in result.stdout
    assert "official neuron count (approx.): 8" in result.stdout
    assert "consistent with the normalized tables: True" in result.stdout


# --------------------------------------------------------------------------------- docs
def test_data_md_documents_the_distinction() -> None:
    text = (PROJECT_ROOT / "DATA.md").read_text()
    assert "Source Dataset vs Canonical Simulation Graph" in text
    assert "165,122" in text and "166,700" in text and CANONICAL_RULE in text


def test_readme_never_presents_canonical_count_as_census() -> None:
    lines = (PROJECT_ROOT / "README.md").read_text().splitlines()
    mentions = [line for line in lines if "165,122" in line]
    assert mentions, "README must state the canonical graph size"
    for line in mentions:
        assert re.search(r"canonical", line, re.IGNORECASE), line
