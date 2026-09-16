"""Smoke-level tests of the CLI scripts on the synthetic fixture and synthetic raw files."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.connectome import Provenance
from tests.synthetic_malecns import EXPECTED_TRACED_EDGES, TRACED_IDS, write_synthetic_malecns_raw

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def test_normalize_and_inspect_fixture(tmp_path) -> None:
    out = tmp_path / "out"
    result = run(
        str(SCRIPTS / "normalize_dataset.py"), "--adapter", "fixture", "--out-dir", str(out)
    )
    assert result.returncode == 0, result.stderr
    for name in (
        "neurons.parquet",
        "connections.parquet",
        "provenance.json",
        "inspection_report.json",
        "inspection_report.md",
    ):
        assert (out / name).is_file(), name
    provenance = Provenance.read(out / "provenance.json")
    assert provenance.synthetic is True
    assert provenance.counts == {
        "neurons": 8,
        "connections": 11,
        "dangling": {
            "total_edges_raw": 13,
            "kept_edges": 11,
            "pre_unknown_only": 1,
            "post_unknown_only": 1,
            "both_unknown": 0,
            "kept_dangling": False,
            "dangling_edges": 2,
        },
    }
    assert provenance.transform_script == "scripts/normalize_dataset.py"

    inspect = run(str(SCRIPTS / "inspect_dataset.py"), "--processed-dir", str(out), "--json")
    assert inspect.returncode == 0, inspect.stderr
    report = json.loads(inspect.stdout)
    assert (
        report["neurons"] == 8
        and report["directed_connections"] == 11
        and report["synthetic"] is True
    )


def test_inspect_fixture_in_memory() -> None:
    result = run(str(SCRIPTS / "inspect_dataset.py"), "--fixture", "--keep-dangling")
    assert result.returncode == 0, result.stderr
    assert "synthetic fixture: True" in result.stdout
    assert "either 2" in result.stdout  # both dangling edges reported


def test_inspect_missing_processed_data(tmp_path) -> None:
    strict = run(str(SCRIPTS / "inspect_dataset.py"), "--processed-dir", str(tmp_path))
    assert strict.returncode == 1 and "no normalized data" in strict.stderr
    lenient = run(
        str(SCRIPTS / "inspect_dataset.py"), "--processed-dir", str(tmp_path), "--allow-missing"
    )
    assert lenient.returncode == 0 and "no normalized data" in lenient.stdout


def test_normalize_malecns_path_with_synthetic_raw_files(tmp_path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "out"
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
    provenance = Provenance.read(out / "provenance.json")
    assert provenance.dataset_name == "male-cns" and provenance.dataset_version == "v1.0"
    assert provenance.license and "CC-BY" in provenance.license
    assert provenance.counts["neurons"] == len(TRACED_IDS)
    assert provenance.counts["connections"] == len(EXPECTED_TRACED_EDGES)
    assert provenance.normalization["neuron_set_rule"] == ["Traced"]
    assert provenance.normalization["column_mapping"]["synapse_count"] == "weight"
    assert {entry.role for entry in provenance.raw_files} == {
        "annotations",
        "weights",
        "neurotransmitters",
    }


def test_normalize_refuses_checksum_mismatch(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_synthetic_malecns_raw(raw)
    result = run(
        str(SCRIPTS / "normalize_dataset.py"),
        "--adapter",
        "malecns",
        "--raw-dir",
        str(raw),
        "--out-dir",
        str(tmp_path / "out"),
    )
    assert result.returncode == 1
    assert "checksum mismatch" in result.stderr
    assert not (tmp_path / "out" / "neurons.parquet").exists()


@pytest.mark.parametrize("script", ["normalize_dataset.py", "inspect_dataset.py"])
def test_scripts_have_help(script: str) -> None:
    result = run(str(SCRIPTS / script), "--help")
    assert result.returncode == 0 and "usage" in result.stdout.lower()
