import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def test_run_simulation_on_fixture(tmp_path) -> None:
    result = run(
        str(SCRIPTS / "run_simulation.py"),
        "--fixture",
        "--stimulate",
        "syn_001",
        "--intensity",
        "2.0",
        "--duration",
        "3",
        "--steps",
        "30",
        "--simulation-id",
        "cli_sim",
        "--out-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "NOT MEASURED MALECNS PARAMETERS" in result.stdout
    assert "firing_events=6 neurons_activated=6" in result.stdout
    report = json.loads((tmp_path / "cli_sim.report.json").read_text())
    assert report["run"]["per_step_fired_counts"][:3] == [1, 2, 3]
    assert report["circuit_hash"] and "SIMULATED" in report["label"]
    assert (tmp_path / "cli_sim.snapshot.json").is_file()


def test_run_simulation_fails_loudly(tmp_path) -> None:
    unknown = run(
        str(SCRIPTS / "run_simulation.py"),
        "--fixture",
        "--stimulate",
        "ghost",
        "--steps",
        "5",
        "--out-dir",
        str(tmp_path),
    )
    assert unknown.returncode == 1 and "UnknownNeuronError" in unknown.stderr
    bad_config = run(
        str(SCRIPTS / "run_simulation.py"),
        "--fixture",
        "--stimulate",
        "syn_001",
        "--steps",
        "5",
        "--config-json",
        '{"threshold": -1}',
        "--out-dir",
        str(tmp_path),
    )
    assert bad_config.returncode == 1 and "ValidationError" in bad_config.stderr
    assert not list(tmp_path.iterdir())


def test_smoke_simulation_fixture_only(tmp_path) -> None:
    result = run(str(SCRIPTS / "smoke_simulation.py"), "--fixture-only", "--out-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "fixture: firing events=6" in result.stdout and result.stdout.strip().endswith("PASS")
