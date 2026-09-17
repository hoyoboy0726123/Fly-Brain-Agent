"""P7.1 Virtual Threat Lab API: ``GET /embodiment/config`` and ``POST /embodiment/run``.

The API is a thin reshaping of the P7.0 ``EmbodiedAgentLoop``. These tests compare the API
timeline against a direct P7.0 loop run with the same configuration (same brain, same seed)
so that the replay data shown by the frontend is provably the backend's own record.
Happy paths run against the committed ``escape_v1`` artifact and are never mocked.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.embodiment import (
    EXPERIMENT_NAME,
    LABELS,
    MAX_LOOP_STEPS,
    SCIENTIFIC_BOUNDARIES,
    ThreatLabRunResponse,
)
from app.behavior import load_escape_config
from app.config import Settings
from app.embodiment import (
    EMBODIMENT_DISCLAIMER,
    EmbodiedAgentLoop,
    EscapeMotorAdapter,
    LoopConfig,
    SimpleBodyAdapter,
    SimpleWorldAdapter,
    SimpleWorldConfig,
    VirtualLoomingSensor,
)
from app.main import create_app
from app.sensors import LoomingStimulus
from app.simulation.errors import NumericalInstabilityError

CONFIG = load_escape_config("escape_v1")
GROUP_KEYS = {"LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R", "DNp01_L", "DNp01_R"}
STEP_KEYS = {"step_index", "simulation_time", "dt", "world", "body", "sensor", "brain", "motor"}


def run(client: TestClient, **body) -> dict:
    response = client.post("/embodiment/run", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def direct_loop(client: TestClient, request: dict) -> EmbodiedAgentLoop:
    """The P7.0 loop the API claims to expose, built independently with the same inputs."""
    world = request.get("world", {})
    loop = EmbodiedAgentLoop(
        world=SimpleWorldAdapter(SimpleWorldConfig(**world)),
        sensor=VirtualLoomingSensor(),
        brain=client.app.state.escape.get().experiment,
        motor=EscapeMotorAdapter(),
        body=SimpleBodyAdapter(),
        config=LoopConfig(
            dt=0.1, max_steps=request.get("max_steps", 30), random_seed=request.get("seed", 0)
        ),
    )
    loop.reset()
    loop.run(request.get("max_steps", 30))
    return loop


def vec(v) -> tuple[float, float, float]:
    return (v["x"], v["y"], v["z"]) if isinstance(v, dict) else (v.x, v.y, v.z)


# ----------------------------------------------------------------------------- config
def test_config_describes_experiment_world_sensor_body_motor_and_timing(
    client: TestClient,
) -> None:
    response = client.get("/embodiment/config")
    assert response.status_code == 200, response.text
    cfg = response.json()
    assert cfg["experiment_name"] == EXPERIMENT_NAME == "virtual_threat_lab_v1"
    assert cfg["world_config"]["start_distance"] == 20.0
    assert cfg["world_config"]["approach_speed"] == 10.0
    assert cfg["sensor_config"]["saturation_angle_rad"] == pytest.approx(math.pi / 2)
    assert cfg["body_config"]["label"].startswith("COMPUTATIONAL BODY PARAMETERS")
    assert cfg["motor_config"]["label"].startswith("COMPUTATIONAL MOTOR PARAMETERS")
    assert cfg["sensor_config"]["label"].startswith("COMPUTATIONAL SENSOR PARAMETERS")
    assert cfg["loop_config"]["dt"] == 0.1
    timing = cfg["timing"]
    assert timing["loop_dt"] == 0.1 and timing["neural_steps_per_loop_step"] == 30
    assert "not claimed to be physically related" in timing["note"]
    assert cfg["max_loop_steps"] == MAX_LOOP_STEPS
    assert cfg["run_request_limits"]["max_steps"]["max"] == MAX_LOOP_STEPS
    assert "not exposed" in cfg["run_request_limits"]["neural_parameters"]
    assert "dimensionless" in cfg["units_note"]


def test_config_reports_circuit_dataset_boundaries_labels_and_disclaimer(
    client: TestClient,
) -> None:
    cfg = client.get("/embodiment/config").json()
    circuit = cfg["circuit"]
    assert circuit["circuit_id"] == "escape_v1"
    assert circuit["circuit_hash"] == CONFIG.expected_circuit_hash
    assert circuit["neurons"] == 286 and circuit["edges"] == 932
    assert circuit["biological_status"] == "PARTIALLY SUPPORTED"
    assert circuit["research_document"] == "docs/circuits/escape_v1.md"
    assert cfg["dataset"] == "male-cns" and cfg["dataset_version"] == "v1.0"
    assert cfg["escape_config_version"] == CONFIG.config_version
    assert cfg["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert cfg["labels"] == LABELS
    assert cfg["labels"] == {
        "world_physics": "COMPUTATIONAL",
        "virtual_sensing": "COMPUTATIONAL SENSOR INPUT",
        "neural_activity": "SIMULATED",
        "structural_connectivity": "BIOLOGICAL DATA",
        "body": "SIMPLIFIED COMPUTATIONAL BODY",
        "motor_mapping": "COMPUTATIONAL MOTOR MAPPING",
    }
    assert cfg["scientific_boundaries"] == SCIENTIFIC_BOUNDARIES
    assert {b["label"] for b in cfg["scientific_boundaries"]} >= {
        "BIOLOGICAL DATA",
        "SIMULATED",
        "COMPUTATIONAL SENSOR INPUT",
        "COMPUTATIONAL MOTOR MAPPING",
        "SIMPLIFIED COMPUTATIONAL BODY",
        "COMPUTATIONAL WORLD",
    }
    assert {g["key"] for g in cfg["groups"]} == GROUP_KEYS
    assert cfg["group_edges"], "group edges come from the artifact"


# ----------------------------------------------------------------------------- run: shape
def test_run_returns_experiment_id_provenance_timeline_outcome_and_disclaimer(
    client: TestClient,
) -> None:
    result = run(client)
    ThreatLabRunResponse.model_validate(result)
    assert result["experiment_id"] and result["experiment_name"] == EXPERIMENT_NAME
    assert result["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert result["labels"] == LABELS
    assert result["request"] == {
        "experiment": EXPERIMENT_NAME,
        "seed": 0,
        "max_steps": 30,
        "world": {"start_distance": 20.0, "approach_speed": 10.0, "azimuth_deg": 0.0},
    }
    assert len(result["timeline"]) == 30 == result["outcome"]["loop_steps"]
    assert set(result["timeline"][0]) == STEP_KEYS
    assert result["runtime_seconds"] >= 0.0
    assert result["initial_world"]["objects"][0]["position"] == {"x": 20.0, "y": 0.0, "z": 0.0}
    assert result["initial_body"]["position"] == {"x": 0.0, "y": 0.0, "z": 0.0}


def test_timeline_steps_are_ordered_and_time_is_monotonic(client: TestClient) -> None:
    timeline = run(client, max_steps=25)["timeline"]
    assert [s["step_index"] for s in timeline] == list(range(25))
    times = [s["simulation_time"] for s in timeline]
    assert all(b > a for a, b in zip(times, times[1:], strict=False))
    assert times[0] == 0.0 and times[-1] == pytest.approx(2.4)
    assert all(s["dt"] == 0.1 and s["world"]["step_index"] == s["step_index"] for s in timeline)
    assert all(
        s["world"]["simulation_time"] == pytest.approx(s["simulation_time"]) for s in timeline
    )


def test_every_step_carries_all_five_labelled_stages(client: TestClient) -> None:
    for step in run(client, max_steps=8)["timeline"]:
        assert step["world"]["label"] == "COMPUTATIONAL WORLD"
        assert step["sensor"]["label"].startswith("COMPUTATIONAL SENSOR INPUT")
        assert step["brain"]["label"] == "SIMULATED NEURAL ACTIVITY"
        assert step["motor"]["label"].startswith("COMPUTATIONAL MOTOR MAPPING")
        assert step["body"]["label"].startswith("SIMPLIFIED COMPUTATIONAL BODY")
        assert step["motor"]["direction_decoded"] is False
        assert set(step["brain"]["group_fired_counts"]) == GROUP_KEYS
        assert step["brain"]["action"] in ("NO_ACTION", "ESCAPE")
        assert step["motor"]["command"] in ("IDLE", "ESCAPE")


# ----------------------------------------------------------------------------- run: fidelity
@pytest.mark.parametrize(
    "request_body",
    [
        {},
        {"seed": 7, "max_steps": 12, "world": {"azimuth_deg": 60.0, "start_distance": 8.0}},
        {"max_steps": 20, "world": {"approach_speed": 4.0}},
    ],
)
def test_world_body_and_sensor_match_the_p7_0_loop_records(
    client: TestClient, request_body: dict
) -> None:
    result = run(client, **request_body)
    loop = direct_loop(client, request_body)
    records = loop.records
    assert len(result["timeline"]) == len(records)
    # world/body shown at step N are the states the sensor observed at step N
    # (= the initial state for step 1, the post-step state of N-1 afterwards).
    for index, (step, record) in enumerate(zip(result["timeline"], records, strict=True)):
        if index == 0:
            world_before, body_before = loop.initial_world, loop.initial_body
        else:
            world_before = records[index - 1].world_state
            body_before = records[index - 1].body_state
        obj = world_before.objects[0]
        api_obj = step["world"]["objects"][0]
        assert vec(api_obj["position"]) == pytest.approx(vec(obj.position))
        assert vec(api_obj["velocity"]) == pytest.approx(vec(obj.velocity))
        assert api_obj["size"] == obj.size and api_obj["object_type"] == obj.object_type
        assert step["world"]["simulation_time"] == pytest.approx(world_before.simulation_time)
        assert vec(step["body"]["position"]) == pytest.approx(vec(body_before.position))
        assert vec(step["body"]["velocity"]) == pytest.approx(vec(body_before.linear_velocity))
        assert step["body"]["heading"] == pytest.approx(body_before.heading)
        assert step["body"]["grounded"] is body_before.grounded
        obs = record.observation
        assert step["sensor"]["intensity"] == pytest.approx(obs.values["intensity"])
        assert step["sensor"]["distance"] == pytest.approx(obs.values["distance"])
        assert step["sensor"]["angular_size_rad"] == pytest.approx(obs.values["angular_size_rad"])
        assert step["sensor"]["bearing_rad"] == pytest.approx(obs.values["bearing_rad"])
        assert step["sensor"]["direction"] == obs.metadata["direction"]
        assert step["sensor"]["visible"] is bool(obs.values["visible"])
        assert step["brain"]["stimulus"] == record.stimulus


def test_action_and_motor_command_match_the_p7_0_loop_records(client: TestClient) -> None:
    result = run(client)
    records = direct_loop(client, {}).records
    for step, record in zip(result["timeline"], records, strict=True):
        assert step["brain"]["action"] == record.brain.action
        assert step["brain"]["activity_label"] == record.brain.activity_label
        assert step["motor"]["command"] == str(record.command.command)
        assert step["motor"]["magnitude"] == record.command.magnitude
        assert (
            step["motor"]["source_action"]
            == record.command.source_action
            == step["brain"]["action"]
        )
        assert (step["motor"]["command"] == "ESCAPE") == (step["brain"]["action"] == "ESCAPE")
    outcome = result["outcome"]
    summary = direct_loop(client, {}).record().summary
    assert outcome["first_escape_step"] == summary["first_escape_step"]
    assert outcome["actions"] == summary["actions"] and outcome["commands"] == summary["commands"]
    assert outcome["displacement"] == pytest.approx(summary["displacement"])
    assert outcome["escape_steps"] == [
        s["step_index"] for s in result["timeline"] if s["motor"]["command"] == "ESCAPE"
    ]


def test_group_activity_is_the_simulated_activity_of_the_recorded_stimulus(
    client: TestClient,
) -> None:
    """The brain panel data must be the P4 simulation's own group counts — not a UI rule."""
    result = run(client)
    experiment = client.app.state.escape.get().experiment
    escape_step = result["outcome"]["first_escape_step"]
    assert escape_step is not None, "default world is expected to trigger an ESCAPE"
    for step in (result["timeline"][0], result["timeline"][escape_step]):
        stimulus = LoomingStimulus(**step["brain"]["stimulus"])
        direct = experiment.run(stimulus, steps=step["brain"]["neural_steps"])
        assert step["brain"]["group_fired_counts"] == direct.group_activity.fired_counts
        assert step["brain"]["action"] == str(direct.decision.action)
        assert step["brain"]["firing_events"] == direct.firing_events
        assert step["brain"]["neurons_activated"] == direct.neurons_activated
        assert step["brain"]["first_output_fire_step"] == direct.decision.first_output_fire_step
        for key, counts in step["brain"]["group_fired_counts"].items():
            assert len(counts) == step["brain"]["neural_steps"]
            assert step["brain"]["group_peak_fired"][key] == max(counts)
    quiet, loud = result["timeline"][0]["brain"], result["timeline"][escape_step]["brain"]
    assert sum(map(sum, quiet["group_fired_counts"].values())) == 0
    assert quiet["action"] == "NO_ACTION" and quiet["sensory_first_fire_step"] is None
    assert loud["group_peak_fired"]["DNp01_L"] == 1 and loud["group_peak_fired"]["DNp01_R"] == 1
    assert loud["sensory_first_fire_step"] is not None
    assert loud["sensory_first_fire_step"] <= loud["first_output_fire_step"]


def test_no_activity_appears_before_the_sensor_drives_the_brain(client: TestClient) -> None:
    """Looming intensity below the model's response never yields fabricated activity."""
    result = run(client, max_steps=5, world={"start_distance": 60.0, "approach_speed": 1.0})
    for step in result["timeline"]:
        assert step["brain"]["action"] == "NO_ACTION" and step["motor"]["command"] == "IDLE"
        assert step["brain"]["firing_events"] == 0
        assert vec(step["body"]["position"]) == (0.0, 0.0, 0.0)
    assert result["outcome"]["first_escape_step"] is None
    assert result["outcome"]["events"] == []


def test_body_moves_only_after_an_escape_command(client: TestClient) -> None:
    result = run(client)
    first = result["outcome"]["first_escape_step"]
    assert first is not None
    timeline = result["timeline"]
    assert timeline[first]["motor"]["command"] == "ESCAPE"
    for step in timeline[: first + 1]:  # up to and including the step that decodes ESCAPE
        assert vec(step["body"]["position"]) == (0.0, 0.0, 0.0) and step["body"]["grounded"]
    after = timeline[first + 1]  # the body state observed one loop step later
    assert after["body"]["position"]["x"] > 0.0 and after["body"]["position"]["z"] > 0.0
    assert after["body"]["grounded"] is False
    assert result["outcome"]["displacement"] > 0.0
    kinds = [(e["kind"], e["step_index"]) for e in result["outcome"]["events"]]
    assert kinds[0] == ("first_escape", first)
    assert all(k in ("first_escape", "escape", "landed") for k, _ in kinds)
    landed = [i for k, i in kinds if k == "landed"]
    if landed:
        assert timeline[landed[0]]["body"]["grounded"] is True
        assert timeline[landed[0] - 1]["body"]["grounded"] is False
    else:
        assert result["outcome"]["final_grounded"] is False


def test_object_approaches_and_looming_input_grows(client: TestClient) -> None:
    timeline = run(client)["timeline"]
    first = next(s["step_index"] for s in timeline if s["motor"]["command"] == "ESCAPE")
    approach = timeline[:first]
    distances = [s["sensor"]["distance"] for s in approach]
    intensities = [s["sensor"]["intensity"] for s in approach]
    assert all(b < a for a, b in zip(distances, distances[1:], strict=False))
    assert all(b > a for a, b in zip(intensities, intensities[1:], strict=False))
    xs = [s["world"]["objects"][0]["position"]["x"] for s in approach]
    assert xs[0] == 20.0 and all(b < a for a, b in zip(xs, xs[1:], strict=False))


def test_azimuth_changes_direction_without_any_neural_change(client: TestClient) -> None:
    left = run(client, max_steps=5, world={"azimuth_deg": 60.0, "start_distance": 8.0})
    right = run(client, max_steps=5, world={"azimuth_deg": -60.0, "start_distance": 8.0})
    assert {s["sensor"]["direction"] for s in left["timeline"]} == {"left"}
    assert {s["sensor"]["direction"] for s in right["timeline"]} == {"right"}
    assert left["provenance"]["simulation_config"] == right["provenance"]["simulation_config"]
    assert left["provenance"]["circuit_hash"] == right["provenance"]["circuit_hash"]


# ----------------------------------------------------------------------------- provenance
def test_provenance_records_data_brain_adapters_and_disclaimer(client: TestClient) -> None:
    result = run(client, seed=5, max_steps=3, world={"approach_speed": 2.0})
    prov = result["provenance"]
    assert prov["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert prov["dataset"] == "male-cns" and prov["dataset_version"] == "v1.0"
    assert prov["circuit_id"] == "escape_v1"
    assert prov["circuit_hash"] == CONFIG.expected_circuit_hash
    assert prov["biological_status"] == "PARTIALLY SUPPORTED"
    assert prov["escape_config_version"] == CONFIG.config_version
    assert prov["random_seed"] == 5
    assert prov["world_adapter"] == "SimpleWorldAdapter"
    assert prov["world_config"]["approach_speed"] == 2.0
    assert prov["sensor_adapter"] == "VirtualLoomingSensor"
    assert prov["motor_adapter"] == "EscapeMotorAdapter"
    assert prov["body_adapter"] == "SimpleBodyAdapter"
    assert prov["loop_config"]["max_steps"] == 3
    assert prov["timing"]["neural_steps_per_loop_step"] == 30
    assert prov["simulation_config"] == client.get("/escape/config").json()["simulation_config"]


def test_disclaimer_is_exact_everywhere(client: TestClient) -> None:
    result = run(client, max_steps=2)
    expected = (
        "Structural connectivity is biological data. Neural activity is simulated. "
        "Virtual sensing, motor mapping, body dynamics, and world physics are computational "
        "interpretations."
    )
    assert EMBODIMENT_DISCLAIMER == expected
    assert result["disclaimer"] == expected == result["provenance"]["disclaimer"]
    assert client.get("/embodiment/config").json()["disclaimer"] == expected


# ----------------------------------------------------------------------------- determinism
def test_same_seed_and_world_is_deterministic(client: TestClient) -> None:
    a = run(client, seed=11, max_steps=20)
    b = run(client, seed=11, max_steps=20)
    assert a["experiment_id"] != b["experiment_id"]
    assert a["timeline"] == b["timeline"]
    assert a["outcome"] == b["outcome"]
    assert a["provenance"] == b["provenance"]


def test_runs_are_isolated_from_each_other_and_from_the_escape_service(
    client: TestClient,
) -> None:
    escape_before = client.post(
        "/escape/run", json={"stimulus": "looming", "direction": "center", "intensity": 0.5}
    ).json()
    baseline = run(client)
    other = run(client, max_steps=10, world={"start_distance": 5.0, "approach_speed": 1.0})
    again = run(client)
    assert again["timeline"] == baseline["timeline"], "an earlier run must not leak state"
    assert other["timeline"][0]["world"]["objects"][0]["position"]["x"] == 5.0
    assert baseline["timeline"][0]["world"]["objects"][0]["position"]["x"] == 20.0
    escape_after = client.post(
        "/escape/run", json={"stimulus": "looming", "direction": "center", "intensity": 0.5}
    ).json()
    for key in ("action", "timeline", "sensory_activity", "output_activity", "circuit_hash"):
        assert escape_before[key] == escape_after[key]
    service = client.app.state.escape.get()
    assert service.experiment.config.model_dump() == CONFIG.model_dump()


# ----------------------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "body",
    [
        {"neural_gain": 2.0},
        {"threshold": -50.0},
        {"simulation": {"threshold": -50.0}},
        {"stimulus": {"intensity": 1.0}},
        {"experiment": "other"},
        {"seed": -1},
        {"seed": "abc"},
        {"max_steps": 0},
        {"max_steps": 1.5},
        {"world": {"start_distance": 0.0}},
        {"world": {"start_distance": 1000.0}},
        {"world": {"approach_speed": -1.0}},
        {"world": {"azimuth_deg": 181.0}},
        {"world": {"object_size": 5.0}},
        {"world": {"gravity": 9.8}},
        {"world": None},
        "not json",
    ],
)
def test_invalid_or_neural_tuning_requests_are_rejected_with_422(client: TestClient, body) -> None:
    response = client.post("/embodiment/run", json=body)
    assert response.status_code == 422, response.text


def test_run_limit_is_enforced(client: TestClient) -> None:
    assert client.post("/embodiment/run", json={"max_steps": MAX_LOOP_STEPS + 1}).status_code == 422
    result = run(client, max_steps=MAX_LOOP_STEPS, world={"approach_speed": 0.5})
    assert len(result["timeline"]) == MAX_LOOP_STEPS


def test_missing_circuit_yields_503_without_a_timeline(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        for response in (
            client.get("/embodiment/config"),
            client.post("/embodiment/run", json={}),
        ):
            assert response.status_code == 503
            detail = response.json()["detail"]
            assert detail["error"] == "circuit_unavailable"
            assert "timeline" not in response.json()


def test_simulation_failure_yields_500_and_no_partial_timeline(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = client.app.state.escape.get().experiment
    original = experiment.run
    calls = {"n": 0}

    def explode(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise NumericalInstabilityError("membrane potential became NaN at step 3")
        return original(*args, **kwargs)

    monkeypatch.setattr(experiment, "run", explode)
    response = client.post("/embodiment/run", json={"max_steps": 10})
    assert response.status_code == 500
    payload = response.json()
    assert (
        payload["detail"]["error"] == "simulation_error" and "NaN" in payload["detail"]["message"]
    )
    assert "timeline" not in payload and "outcome" not in payload
    monkeypatch.undo()
    assert len(run(client, max_steps=4)["timeline"]) == 4, "service recovers after a failure"


def test_slow_run_yields_504(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, environment="test", escape_run_timeout_seconds=0.02)
    with TestClient(create_app(settings)) as client:
        experiment = client.app.state.escape.get().experiment
        original = experiment.run

        def slow(*args, **kwargs):
            time.sleep(0.2)
            return original(*args, **kwargs)

        monkeypatch.setattr(experiment, "run", slow)
        response = client.post("/embodiment/run", json={"max_steps": 3})
        assert response.status_code == 504
        assert response.json()["detail"]["error"] == "timeout"


# ----------------------------------------------------------------------------- payload / compat
def test_payload_carries_group_activity_but_no_per_neuron_states(client: TestClient) -> None:
    response = client.post("/embodiment/run", json={})
    text = response.text
    assert "neuron_activity" not in text and "membrane" not in text
    assert "group_fired_counts" in text
    assert len(response.content) < 400_000, "30-step replay payload stays small"


def test_p5_and_p6_apis_are_unchanged(client: TestClient) -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/embodiment/config", "/embodiment/run"} <= paths
    assert {"/escape/config", "/escape/run", "/health"} <= paths
    assert {
        "/circuits",
        "/circuits/{circuit_id}",
        "/circuits/{circuit_id}/nodes",
        "/circuits/{circuit_id}/edges",
        "/circuits/{circuit_id}/provenance",
        "/circuits/{circuit_id}/neurons/{neuron_id}",
        "/circuits/{circuit_id}/neurons/{neuron_id}/neighbors",
        "/circuits/{circuit_id}/edges/{pre_neuron_id}/{post_neuron_id}",
    } <= paths
    escape = client.post(
        "/escape/run", json={"stimulus": "looming", "direction": "center", "intensity": 0.5}
    )
    assert escape.status_code == 200 and escape.json()["action"] == "ESCAPE"
    circuits = client.get("/circuits")
    assert circuits.status_code == 200
    provenance = client.get("/circuits/escape_v1/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["circuit_hash"] == CONFIG.expected_circuit_hash
