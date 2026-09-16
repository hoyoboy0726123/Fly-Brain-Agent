"""P5 escape API: config, run, validation, error contract and WebSocket stream.

These tests run against the committed ``data/circuits/escape_v1.json`` artifact (286
neurons / 932 edges, hash-verified) and need no raw dataset. The happy path is never mocked.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.escape import SCIENTIFIC_LABELS, EscapeRunResponse, socket_events
from app.behavior import DISCLAIMER, load_escape_config
from app.circuits import Circuit
from app.config import Settings
from app.main import create_app
from app.simulation.errors import NumericalInstabilityError

CONFIG = load_escape_config("escape_v1")
ARTIFACT = Settings(_env_file=None).circuits_data_dir / "escape_v1.json"
RUN_KEYS = {
    "experiment_id",
    "stimulus",
    "circuit_id",
    "circuit_hash",
    "timeline",
    "sensory_activity",
    "output_activity",
    "action",
    "disclaimer",
}


def run(client: TestClient, direction: str, intensity: float, **extra) -> dict:
    body = {"stimulus": "looming", "direction": direction, "intensity": intensity, **extra}
    response = client.post("/escape/run", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_committed_artifact_is_present() -> None:
    assert ARTIFACT.is_file(), "data/circuits/escape_v1.json must be committed for the demo"


# ----------------------------------------------------------------------------- config
def test_config_endpoint_reports_verified_circuit_and_disclaimer(client: TestClient) -> None:
    response = client.get("/escape/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["biological_status"] == "PARTIALLY SUPPORTED"
    assert payload["circuit_id"] == "escape_v1"
    assert payload["circuit_hash"] == CONFIG.expected_circuit_hash
    assert payload["circuit_verified"] is True
    assert payload["dataset"] == "male-cns" and payload["dataset_version"] == "v1.0"
    assert payload["circuit_neurons"] == 286 and payload["circuit_edges"] == 932
    assert payload["actions"] == ["NO_ACTION", "ESCAPE"]
    assert payload["scientific_labels"] == list(SCIENTIFIC_LABELS)
    assert payload["research_document"] == "docs/circuits/escape_v1.md"
    assert "NOT MEASURED" in payload["simulation_config"]["label"]
    assert payload["max_steps"] >= payload["simulation_steps"] == 30


def test_config_groups_match_configured_populations(client: TestClient) -> None:
    payload = client.get("/escape/config").json()
    groups = {g["key"]: g for g in payload["groups"]}
    assert set(groups) == {"LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R", "DNp01_L", "DNp01_R"}
    sensory = [g for g in groups.values() if g["role"] == "sensory"]
    assert (
        sum(g["neuron_count"] for g in sensory)
        == 284
        == sum(payload["stimulated_sensory_counts"].values())
    )
    assert sum(g["neuron_count"] for g in sensory if g["side"] == "L") == 155
    assert sum(g["neuron_count"] for g in sensory if g["side"] == "R") == 129
    assert groups["DNp01_L"]["neuron_count"] == 1 and groups["DNp01_R"]["neuron_count"] == 1
    assert payload["sensory_population_counts"] == {"L": 165, "R": 146}
    assert payload["excluded_sensory_counts"] == {"L": 10, "R": 17}
    assert payload["output_groups"] == {"L": ["10010"], "R": ["10001"]}


def test_config_group_edges_come_from_the_artifact_and_are_ipsilateral(
    client: TestClient,
) -> None:
    payload = client.get("/escape/config").json()
    edges = {(e["pre_key"], e["post_key"]): e for e in payload["group_edges"]}
    assert all(e["dataset"] == "male-cns" for e in edges.values())
    for pre, post in (("LC4_L", "DNp01_L"), ("LPLC2_L", "DNp01_L"), ("LC4_R", "DNp01_R")):
        assert (pre, post) in edges
    assert not any(pre.endswith("_L") and post.endswith("_R") for pre, post in edges)
    assert not any(pre.endswith("_R") and post.endswith("_L") for pre, post in edges)
    assert sum(e["edge_count"] for e in edges.values()) == 932
    artifact = Circuit.load(ARTIFACT)
    assert sum(e["synapse_total"] for e in edges.values()) == sum(
        e.synapse_count for e in artifact.edges
    )


def test_config_describes_the_three_layers(client: TestClient) -> None:
    layers = client.get("/escape/config").json()["layers"]
    assert [layer["kind"] for layer in layers] == [
        "BIOLOGICAL STRUCTURE",
        "COMPUTATIONAL DYNAMICS",
        "APPLICATION DECODING",
    ]
    assert any("simulated" in layer["description"].lower() for layer in layers)


# ----------------------------------------------------------------------------- run
def test_run_center_half_intensity_escapes_with_both_gf(client: TestClient) -> None:
    payload = run(client, "center", 0.5)
    assert payload["action"] == "ESCAPE"
    assert payload["gf_activity"] == "Both"
    assert payload["sensory_activity"]["first_fire_step"] == 3
    assert payload["sensory_activity"]["stimulated_count"] == 284
    assert payload["decision"]["first_output_fire_step"] == 4
    assert {o["neuron_id"]: o["spike_count"] for o in payload["output_activity"]} == {
        "10010": 1,
        "10001": 1,
    }


def test_run_center_low_intensity_is_no_action(client: TestClient) -> None:
    payload = run(client, "center", 0.2)
    assert payload["action"] == "NO_ACTION"
    assert payload["gf_activity"] == "None"
    assert payload["decision"]["output_spike_count"] == 0
    assert payload["firing_events"] == 0
    assert all(o["spike_count"] == 0 for o in payload["output_activity"])


@pytest.mark.parametrize(
    ("direction", "expected_side"), [("left", "Left"), ("right", "Right"), ("center", "Both")]
)
def test_gf_side_is_metadata_only(client: TestClient, direction: str, expected_side: str) -> None:
    payload = run(client, direction, 1.0)
    assert payload["action"] == "ESCAPE"
    assert payload["gf_activity"] == expected_side
    assert payload["sensory_activity"]["first_fire_step"] == 1
    assert payload["decision"]["first_output_fire_step"] == 2


def test_run_response_has_the_required_fields(client: TestClient) -> None:
    payload = run(client, "center", 0.5)
    assert RUN_KEYS <= set(payload)
    parsed = EscapeRunResponse.model_validate(payload)
    assert parsed.stimulus.direction == "center" and parsed.stimulus.intensity == 0.5
    assert parsed.circuit_id == "escape_v1"
    assert [e.tag for e in parsed.timeline] == [
        "t0_stimulus",
        "t1_sensory_activation",
        "t2_intermediate_activity",
        "t3_output_activation",
        "t4_decoded_action",
    ]
    assert parsed.steps == 30 and parsed.stimulus_duration_steps == 5
    assert "SIMULATED" in parsed.activity_label
    assert parsed.circuit.biological_status == "PARTIALLY SUPPORTED"


def test_action_is_only_no_action_or_escape(client: TestClient) -> None:
    seen = set()
    for direction in ("left", "center", "right"):
        for intensity in (0.0, 0.2, 0.5, 1.0):
            seen.add(run(client, direction, intensity)["action"])
    assert seen == {"NO_ACTION", "ESCAPE"}
    assert not any("LEFT" in a or "RIGHT" in a for a in seen)


def test_disclaimer_is_exact_in_every_run(client: TestClient) -> None:
    for direction in ("left", "right"):
        assert run(client, direction, 0.5)["disclaimer"] == DISCLAIMER
    assert DISCLAIMER == (
        "STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. "
        "STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS."
    )


def test_circuit_hash_matches_config_and_artifact(client: TestClient) -> None:
    payload = run(client, "left", 0.5)
    artifact = Circuit.load(ARTIFACT)
    assert payload["circuit_hash"] == CONFIG.expected_circuit_hash == artifact.compute_hash()
    assert payload["circuit"]["circuit_hash"] == payload["circuit_hash"]


def test_group_activity_is_consistent_with_per_step_counts(client: TestClient) -> None:
    payload = run(client, "left", 1.0)
    fired = payload["group_activity"]["fired_counts"]
    steps = payload["steps"]
    assert all(len(counts) == steps for counts in fired.values())
    per_step = [sum(counts[i] for counts in fired.values()) for i in range(steps)]
    assert per_step == payload["per_step_fired_counts"]
    assert payload["sensory_activity"]["fired_counts_per_step"][0] == 155
    assert fired["DNp01_L"][1] == 1 and sum(fired["DNp01_R"]) == 0
    assert "SIMULATED" in payload["group_activity"]["label"]


def test_runs_are_deterministic(client: TestClient) -> None:
    volatile = {"experiment_id", "created_at", "runtime_seconds"}
    first = {k: v for k, v in run(client, "center", 0.5).items() if k not in volatile}
    second = {k: v for k, v in run(client, "center", 0.5).items() if k not in volatile}
    assert first == second


def test_steps_override_is_honoured(client: TestClient) -> None:
    payload = run(client, "center", 0.5, steps=8)
    assert payload["steps"] == 8 and len(payload["per_step_fired_counts"]) == 8


# ----------------------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "body",
    [
        {"stimulus": "looming", "direction": "center", "intensity": 1.5},
        {"stimulus": "looming", "direction": "center", "intensity": -0.1},
        {"stimulus": "looming", "direction": "center", "intensity": "high"},
        {"stimulus": "looming", "direction": "center"},
        {"stimulus": "looming", "intensity": 0.5},
        {"stimulus": "looming", "direction": "up", "intensity": 0.5},
        {"stimulus": "sound", "direction": "center", "intensity": 0.5},
        {"stimulus": "looming", "direction": "center", "intensity": 0.5, "danger": True},
        {"stimulus": "looming", "direction": "center", "intensity": 0.5, "steps": 0},
        {"stimulus": "looming", "direction": "center", "intensity": 0.5, "steps": 10_000_000},
    ],
)
def test_invalid_requests_are_rejected_with_422(client: TestClient, body: dict) -> None:
    response = client.post("/escape/run", json=body)
    assert response.status_code == 422, response.text
    assert "detail" in response.json()


def test_non_json_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/escape/run", content="not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422


def test_steps_above_deployment_limit_is_invalid_request(client: TestClient) -> None:
    limit = client.get("/escape/config").json()["max_steps"]
    response = client.post(
        "/escape/run", json={"direction": "center", "intensity": 0.5, "steps": limit + 1}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "invalid_request"


# ----------------------------------------------------------------------------- error states
def test_missing_circuit_yields_503_and_health_stays_up(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/escape/config")
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "circuit_unavailable"
        response = client.post("/escape/run", json={"direction": "center", "intensity": 0.5})
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "circuit_unavailable"


def test_circuit_hash_mismatch_yields_503(tmp_path: Path) -> None:
    tampered = CONFIG.model_copy(update={"expected_circuit_hash": "0" * 64})
    config_path = tmp_path / "tampered.json"
    config_path.write_text(json.dumps(tampered.model_dump(mode="json")))
    settings = Settings(_env_file=None, environment="test", escape_config=str(config_path))
    with TestClient(create_app(settings)) as client:
        response = client.post("/escape/run", json={"direction": "center", "intensity": 0.5})
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["error"] == "circuit_mismatch"
        assert "hash" in detail["message"]


def test_missing_config_yields_503(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test", escape_config="does_not_exist")
    with TestClient(create_app(settings)) as client:
        response = client.get("/escape/config")
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "config_unavailable"


def test_simulation_error_yields_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = client.app.state.escape.get()

    def explode(*_args, **_kwargs):
        raise NumericalInstabilityError("membrane potential became NaN at step 3")

    monkeypatch.setattr(service.experiment, "run", explode)
    response = client.post("/escape/run", json={"direction": "center", "intensity": 0.5})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error"] == "simulation_error" and "NaN" in detail["message"]


def test_slow_run_yields_504(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, environment="test", escape_run_timeout_seconds=0.05)
    with TestClient(create_app(settings)) as client:
        service = client.app.state.escape.get()
        original = service.experiment.run

        def slow(*args, **kwargs):
            time.sleep(0.3)
            return original(*args, **kwargs)

        monkeypatch.setattr(service.experiment, "run", slow)
        response = client.post("/escape/run", json={"direction": "center", "intensity": 0.5})
        assert response.status_code == 504
        assert response.json()["detail"]["error"] == "timeout"


# ----------------------------------------------------------------------------- WebSocket
def collect(ws) -> list[dict]:
    events = []
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["event"] in ("experiment_finished", "error"):
            return events


def test_websocket_streams_the_backend_timeline(client: TestClient) -> None:
    rest = run(client, "center", 0.5)
    with client.websocket_connect("/ws/escape") as ws:
        ws.send_text(json.dumps({"stimulus": "looming", "direction": "center", "intensity": 0.5}))
        events = collect(ws)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "stimulus_started" and kinds[-1] == "experiment_finished"
    assert kinds.count("neural_activity") == 30
    assert kinds.count("sensory_activation") == 1 and kinds.count("output_activation") == 1
    assert kinds.index("sensory_activation") < kinds.index("output_activation")
    assert kinds[-2] == "action_decoded"
    steps = [e["step"] for e in events if e["event"] == "neural_activity"]
    assert steps == list(range(1, 31))
    sensory = next(e for e in events if e["event"] == "sensory_activation")
    output = next(e for e in events if e["event"] == "output_activation")
    assert sensory["step"] == 3 and output["step"] == 4
    assert kinds[kinds.index("sensory_activation") - 1] == "neural_activity"
    per_step = [e["fired_total"] for e in events if e["event"] == "neural_activity"]
    assert per_step == rest["per_step_fired_counts"]
    decoded = events[-2]
    assert decoded["action"] == "ESCAPE" and decoded["gf_activity"] == "Both"
    result = events[-1]["result"]
    assert result["action"] == "ESCAPE" and result["disclaimer"] == DISCLAIMER
    assert result["circuit_hash"] == rest["circuit_hash"]
    assert all(e["experiment_id"] == result["experiment_id"] for e in events)
    assert all("SIMULATED" in e["activity_label"] for e in events)


def test_websocket_no_action_run_has_no_activation_events(client: TestClient) -> None:
    with client.websocket_connect("/ws/escape") as ws:
        ws.send_text(json.dumps({"direction": "center", "intensity": 0.2}))
        events = collect(ws)
    kinds = [e["event"] for e in events]
    assert "sensory_activation" not in kinds and "output_activation" not in kinds
    assert events[-2]["action"] == "NO_ACTION" and events[-2]["gf_activity"] == "None"


def test_websocket_rejects_invalid_input_and_stays_open(client: TestClient) -> None:
    with client.websocket_connect("/ws/escape") as ws:
        ws.send_text("not json")
        assert ws.receive_json()["error"] == "invalid_request"
        ws.send_text(json.dumps({"direction": "center", "intensity": 1.5}))
        assert ws.receive_json()["error"] == "invalid_request"
        ws.send_text(json.dumps({"direction": "up", "intensity": 0.5}))
        assert ws.receive_json()["error"] == "invalid_request"
        ws.send_text(json.dumps({"direction": "left", "intensity": 1.0}))
        assert collect(ws)[-1]["result"]["gf_activity"] == "Left"


def test_websocket_reports_unavailable_circuit(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    with (
        TestClient(create_app(settings)) as client,
        client.websocket_connect("/ws/escape") as ws,
    ):
        ws.send_text(json.dumps({"direction": "center", "intensity": 0.5}))
        event = ws.receive_json()
        assert event["event"] == "error" and event["error"] == "circuit_unavailable"


def test_socket_events_are_derived_from_the_result_not_recomputed(client: TestClient) -> None:
    result = EscapeRunResponse.model_validate(run(client, "right", 0.5))
    events = socket_events(result)
    t1 = next(e for e in result.timeline if e.tag == "t1_sensory_activation")
    t3 = next(e for e in result.timeline if e.tag == "t3_output_activation")
    sensory = next(e for e in events if e["event"] == "sensory_activation")
    output = next(e for e in events if e["event"] == "output_activation")
    assert sensory["step"] == t1.step and sensory["count"] == t1.count
    assert output["step"] == t3.step and output["neuron_ids"] == t3.neuron_ids
    activity = [e for e in events if e["event"] == "neural_activity"]
    assert [e["stimulus_active"] for e in activity[:6]] == [True] * 5 + [False]
    by_group = activity[2]["fired_by_group"]
    assert by_group["LPLC2_R"] == 74 and by_group["LC4_R"] == 55 and by_group["LC4_L"] == 0


def test_openapi_documents_the_escape_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/escape/config" in paths and "/escape/run" in paths
