import json
import subprocess
import sys
from pathlib import Path

from app.circuits import Circuit

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def test_extract_circuit_script_on_fixture(tmp_path) -> None:
    result = run(
        str(SCRIPTS / "extract_circuit.py"),
        "--fixture",
        "--circuit-id",
        "cli_fixture",
        "--seeds",
        "syn_001",
        "--targets",
        "syn_007",
        "--max-hops",
        "2",
        "--min-synapses",
        "1",
        "--max-neurons",
        "50",
        "--out-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert (
        "returned neurons=6" in result.stdout
        and "reachable=True minimum_path_length=2" in result.stdout
    )
    circuit = Circuit.load(tmp_path / "cli_fixture.json")
    assert len(circuit.edges) == 9
    assert Circuit.load_edges(tmp_path / "cli_fixture.parquet").num_rows == 9


def test_extract_circuit_script_fails_loudly(tmp_path) -> None:
    missing = run(
        str(SCRIPTS / "extract_circuit.py"),
        "--fixture",
        "--circuit-id",
        "x",
        "--seeds",
        "ghost",
        "--max-hops",
        "1",
        "--min-synapses",
        "1",
        "--max-neurons",
        "5",
        "--out-dir",
        str(tmp_path),
    )
    assert missing.returncode == 1 and "MissingNeuronError" in missing.stderr
    exceeded = run(
        str(SCRIPTS / "extract_circuit.py"),
        "--fixture",
        "--circuit-id",
        "x",
        "--seeds",
        "syn_001",
        "--max-hops",
        "2",
        "--min-synapses",
        "1",
        "--max-neurons",
        "2",
        "--out-dir",
        str(tmp_path),
    )
    assert exceeded.returncode == 1 and "MaxNeuronsExceededError" in exceeded.stderr
    assert not list(tmp_path.iterdir())  # nothing written on failure


def test_smoke_circuit_script_fixture_only(tmp_path) -> None:
    result = run(str(SCRIPTS / "smoke_circuit.py"), "--fixture-only", "--out-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "fixture: nodes=6 edges=9" in result.stdout and result.stdout.strip().endswith("PASS")
    data = json.loads((tmp_path / "fixture_smoke_downstream.json").read_text())
    assert data["dataset"] == "synthetic_tiny_connectome"
