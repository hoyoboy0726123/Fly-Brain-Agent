"""P7.2 A/B API: ``GET /embodiment/intervention/config``, ``POST /embodiment/intervention/compare``.

Happy paths run against the committed escape_v1 artifact (never mocked). No test asserts
whether an intervention prevents or delays ESCAPE — the simulation decides; tests check
matched conditions, provenance, target resolution, structural integrity, synchronisation
metadata, validation and failure handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.intervention import (
    COMPARED_CELL_TYPES,
    InterventionCompareResponse,
    InterventionConfigResponse,
)
from app.behavior import BIOLOGICAL_CONTEXT, load_escape_config
from app.config import Settings
from app.embodiment import EMBODIMENT_DISCLAIMER
from app.main import create_app
from app.simulation import INTERVENTION_DISCLAIMER, INTERVENTION_SEMANTICS
from app.simulation.errors import NumericalInstabilityError

CONFIG = load_escape_config("escape_v1")
SELECTORS = ("SILENCE_LC4", "SILENCE_LPLC2", "SILENCE_LC4_LPLC2")


def compare(client: TestClient, selector: str, **body) -> dict:
    response = client.post(
        "/embodiment/intervention/compare", json={"intervention": selector, **body}
    )
    assert response.status_code == 200, response.text
    return response.json()


def cell_type_of(circuit_nodes: dict[str, str], neuron_id: str) -> str | None:
    return circuit_nodes.get(neuron_id)


@pytest.fixture
def circuit_cell_types(client: TestClient) -> dict[str, str]:
    circuit = client.app.state.escape.get().circuit
    return {n.neuron_id: n.cell_type for n in circuit.nodes}


# ----------------------------------------------------------------------------- config
def test_config_resolves_selectors_from_the_loaded_circuit(
    client: TestClient, circuit_cell_types: dict[str, str]
) -> None:
    response = client.get("/embodiment/intervention/config")
    assert response.status_code == 200, response.text
    cfg = response.json()
    InterventionConfigResponse.model_validate(cfg)
    assert cfg["label"] == "COMPUTATIONAL FIRING SUPPRESSION"
    assert cfg["layer"] == "COMPUTATIONAL DYNAMICS"
    assert cfg["semantics"] == INTERVENTION_SEMANTICS
    assert cfg["intervention_disclaimer"] == INTERVENTION_DISCLAIMER
    assert cfg["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert cfg["implemented_types"] == ["NONE", "SUPPRESS_FIRING"]
    assert set(cfg["future_types_not_implemented"]) == {
        "STIMULATE",
        "CLAMP",
        "LESION",
        "REMOVE_CONNECTION",
        "SYNAPTIC_BLOCK",
    }
    selectors = {s["selector"]: s for s in cfg["selectors"]}
    assert set(selectors) == {"CONTROL", "SILENCE_LC4", "SILENCE_LPLC2", "SILENCE_LC4_LPLC2"}
    assert selectors["CONTROL"]["resolved"]["neuron_count"] == 0
    lc4 = sorted(n for n, ct in circuit_cell_types.items() if ct == "LC4")
    lplc2 = sorted(n for n, ct in circuit_cell_types.items() if ct == "LPLC2")
    assert selectors["SILENCE_LC4"]["resolved"]["neuron_ids"] == lc4 and len(lc4) > 0
    assert selectors["SILENCE_LPLC2"]["resolved"]["neuron_ids"] == lplc2 and len(lplc2) > 0
    assert selectors["SILENCE_LC4_LPLC2"]["resolved"]["neuron_ids"] == sorted(lc4 + lplc2)
    assert selectors["SILENCE_LC4_LPLC2"]["resolved"]["per_cell_type_counts"] == {
        "LC4": len(lc4),
        "LPLC2": len(lplc2),
    }
    sig = cfg["structural_signature"]
    assert sig["node_count"] == len(circuit_cell_types) == 286
    assert sig["circuit_hash"] == sig["recorded_hash"] == CONFIG.expected_circuit_hash
    assert cfg["biological_context"] == BIOLOGICAL_CONTEXT
    assert cfg["biological_context"]["citation"]["doi"] == "10.1016/j.cub.2019.01.079"
    assert "not a validation" in cfg["computational_result_label"]
    assert len(cfg["suppression_semantics"]) == 4


# ----------------------------------------------------------------------------- 1-3 comparisons
@pytest.mark.parametrize("selector", SELECTORS)
def test_control_vs_intervention_returns_two_full_trials(
    client: TestClient, selector: str, circuit_cell_types: dict[str, str]
) -> None:
    result = compare(client, selector)
    InterventionCompareResponse.model_validate(result)
    assert result["comparison_id"] and result["request"]["intervention"] == selector
    assert result["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert result["intervention_disclaimer"] == INTERVENTION_DISCLAIMER
    assert result["layer"] == "COMPUTATIONAL DYNAMICS"
    control, treated = result["control"], result["intervention"]
    assert control["role"] == "control" and treated["role"] == "intervention"
    assert control["intervention_config"]["intervention_type"] == "NONE"
    assert treated["intervention_config"]["intervention_type"] == "SUPPRESS_FIRING"
    for trial in (control, treated):
        exp = trial["experiment"]
        assert len(exp["timeline"]) == 30 and exp["experiment_id"]
        assert exp["provenance"]["circuit_hash"] == CONFIG.expected_circuit_hash
        assert set(trial["simulated_firing_totals"]) == set(COMPARED_CELL_TYPES)
    assert control["experiment"]["experiment_id"] != treated["experiment"]["experiment_id"]
    # targeted cell types never produce a simulated spike in the intervention trial …
    targets = set(treated["resolved_targets"]["cell_types"])
    for cell_type in targets:
        assert treated["simulated_firing_totals"][cell_type] == 0
    for step in treated["experiment"]["timeline"]:
        for key, counts in step["brain"]["group_fired_counts"].items():
            if key.rsplit("_", 1)[0] in targets:
                assert sum(counts) == 0
    # … while the control trial is the plain P7.1 run
    plain = client.post("/embodiment/run", json={}).json()
    assert control["experiment"]["timeline"] == plain["timeline"]
    assert control["experiment"]["provenance"]["intervention"] is None
    assert control["suppressed_events"] == 0
    assert treated["suppressed_events"] >= 0  # whatever the model did


# ----------------------------------------------------------------------------- 4 matched
@pytest.mark.parametrize("selector", SELECTORS)
def test_matched_conditions_are_all_true_and_verified(client: TestClient, selector: str) -> None:
    result = compare(client, selector, seed=4, max_steps=12, world={"approach_speed": 6.0})
    matched = result["comparison"]["matched_conditions"]
    assert matched["all_matched"] is True
    assert all(v is True for k, v in matched.items() if k.startswith("same_"))
    assert matched["only_difference"] == "intervention_config"
    cp = result["control"]["experiment"]["provenance"]
    ip = result["intervention"]["experiment"]["provenance"]
    for key in (
        "world_config",
        "sensor_config",
        "body_config",
        "motor_config",
        "simulation_config",
        "random_seed",
        "circuit_hash",
        "dataset_version",
        "timing",
        "loop_config",
    ):
        assert cp[key] == ip[key], key
    assert cp["random_seed"] == ip["random_seed"] == 4
    assert cp["world_config"]["approach_speed"] == 6.0
    assert (
        result["control"]["experiment"]["initial_body"]
        == result["intervention"]["experiment"]["initial_body"]
    )
    assert (
        result["control"]["experiment"]["initial_world"]
        == result["intervention"]["experiment"]["initial_world"]
    )


# ----------------------------------------------------------------------------- 5-9 provenance
def test_intervention_provenance_differs_only_by_the_intervention_block(
    client: TestClient, circuit_cell_types: dict[str, str]
) -> None:
    result = compare(client, "SILENCE_LPLC2")
    cp = result["control"]["experiment"]["provenance"]
    ip = result["intervention"]["experiment"]["provenance"]
    assert cp["intervention"] is None and ip["intervention"] is not None
    assert cp["intervention_layer"] == ip["intervention_layer"] == "COMPUTATIONAL DYNAMICS"
    block = ip["intervention"]
    assert block["intervention_type"] == "SUPPRESS_FIRING"
    assert block["target_cell_types"] == ["LPLC2"]
    assert block["target_neuron_count"] == len(block["target_neuron_ids"]) > 0
    assert all(circuit_cell_types[n] == "LPLC2" for n in block["target_neuron_ids"])
    assert block["layer"] == "COMPUTATIONAL DYNAMICS"
    assert "suppresses simulated firing" in block["semantics"]
    assert {k: v for k, v in cp.items() if k != "intervention"} == {
        k: v for k, v in ip.items() if k != "intervention"
    }
    resolved = result["intervention"]["resolved_targets"]
    assert resolved["selector"] == "SILENCE_LPLC2" and resolved["cell_types"] == ["LPLC2"]
    assert resolved["neuron_ids"] == block["target_neuron_ids"]
    assert resolved["circuit_hash"] == ip["circuit_hash"] == cp["circuit_hash"]
    assert "cell_type annotation" in resolved["resolution_rule"]


def test_same_circuit_hash_seed_and_world_across_both_trials(client: TestClient) -> None:
    result = compare(
        client, "SILENCE_LC4", seed=9, world={"azimuth_deg": 30.0, "start_distance": 12.0}
    )
    c, i = result["control"], result["intervention"]
    assert (
        c["experiment"]["provenance"]["circuit_hash"]
        == i["experiment"]["provenance"]["circuit_hash"]
        == c["structural_signature"]["circuit_hash"]
        == i["structural_signature"]["circuit_hash"]
        == CONFIG.expected_circuit_hash
    )
    assert c["experiment"]["request"]["seed"] == i["experiment"]["request"]["seed"] == 9
    assert (
        c["experiment"]["request"]["world"]
        == i["experiment"]["request"]["world"]
        == {
            "start_distance": 12.0,
            "approach_speed": 10.0,
            "azimuth_deg": 30.0,
        }
    )
    integrity = result["comparison"]["structural_integrity"]
    assert integrity["unchanged"] is True and integrity["before"] == integrity["after"]
    assert integrity["before"]["node_count"] == 286 and integrity["before"]["edge_count"] == 932


def test_resolved_target_count_is_positive_and_from_the_circuit(
    client: TestClient, circuit_cell_types: dict[str, str]
) -> None:
    for selector in SELECTORS:
        resolved = compare(client, selector, max_steps=2)["intervention"]["resolved_targets"]
        assert resolved["neuron_count"] > 0
        assert set(resolved["neuron_ids"]) <= set(circuit_cell_types)
        assert {circuit_cell_types[n] for n in resolved["neuron_ids"]} == set(
            resolved["cell_types"]
        )


# ----------------------------------------------------------------------------- 10 synchronisation
def test_timeline_synchronization_metadata(client: TestClient) -> None:
    result = compare(client, "SILENCE_LC4_LPLC2", max_steps=17)
    sync = result["comparison"]["synchronization"]
    assert sync["control_steps"] == sync["intervention_steps"] == sync["shared_steps"] == 17
    assert sync["cursor_max"] == 16
    assert "trial has ended" in sync["note"]
    control_steps = [s["step_index"] for s in result["control"]["experiment"]["timeline"]]
    treated_steps = [s["step_index"] for s in result["intervention"]["experiment"]["timeline"]]
    assert control_steps == treated_steps == list(range(17))
    times_c = [s["simulation_time"] for s in result["control"]["experiment"]["timeline"]]
    times_i = [s["simulation_time"] for s in result["intervention"]["experiment"]["timeline"]]
    assert times_c == times_i


# ----------------------------------------------------------------------------- 11 no hard-coding
def test_outcome_is_the_models_and_differences_are_descriptive_only(client: TestClient) -> None:
    """Whatever the model does is reported; the response never encodes an expected result."""
    for selector in SELECTORS:
        result = compare(client, selector)
        diff = result["comparison"]["differences"]
        i_exp = result["intervention"]["experiment"]
        # every reported number is recomputable from the returned timelines
        actions = [s["brain"]["action"] for s in i_exp["timeline"]]
        assert diff["intervention_escape_occurred"] == ("ESCAPE" in actions)
        assert diff["intervention_first_escape_step"] == (
            actions.index("ESCAPE") if "ESCAPE" in actions else None
        )
        assert diff["intervention_escape_steps"] == i_exp["outcome"]["escape_steps"]
        assert diff["intervention_actions"] == i_exp["outcome"]["actions"]
        totals = diff["simulated_firing_totals"]
        for cell_type in COMPARED_CELL_TYPES:
            recomputed = sum(
                sum(counts)
                for s in i_exp["timeline"]
                for key, counts in s["brain"]["group_fired_counts"].items()
                if key.rsplit("_", 1)[0] == cell_type
            )
            assert totals[cell_type]["intervention"] == recomputed
            assert totals[cell_type]["delta"] == (
                totals[cell_type]["intervention"] - totals[cell_type]["control"]
            )
        assert diff["intervention_final_displacement"] == i_exp["outcome"]["displacement"]
        assert diff["label"].startswith("CURRENT COMPUTATIONAL RESULT")
        assert diff["summary"][0].startswith("In the current computational model")
        assert not any("real fl" in line.lower() for line in diff["summary"])
        assert "not a biological interpretation" in " ".join(diff["summary"])
    # an A/A comparison is allowed and identical
    aa = compare(client, "CONTROL", max_steps=5)
    assert aa["control"]["experiment"]["timeline"] == aa["intervention"]["experiment"]["timeline"]
    assert aa["comparison"]["differences"]["first_divergent_step"] is None
    assert "A/A" in aa["comparison"]["differences"]["summary"][0]


def test_intervention_trial_is_deterministic_and_matches_the_p7_1_endpoint_shape(
    client: TestClient,
) -> None:
    a = compare(client, "SILENCE_LPLC2", seed=2)
    b = compare(client, "SILENCE_LPLC2", seed=2)
    assert (
        a["intervention"]["experiment"]["timeline"] == b["intervention"]["experiment"]["timeline"]
    )
    assert a["control"]["experiment"]["timeline"] == b["control"]["experiment"]["timeline"]
    assert a["comparison"]["differences"] == b["comparison"]["differences"]
    assert set(a["intervention"]["experiment"]) == set(
        client.post("/embodiment/run", json={}).json()
    )


# ----------------------------------------------------------------------------- 12 validation
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"intervention": "SILENCE_GF"},
        {"intervention": "STIMULATE_LC4"},
        {"intervention": "silence_lc4"},
        {"intervention": None},
        {"intervention": "SILENCE_LC4", "target_neuron_ids": ["10010"]},
        {"intervention": "SILENCE_LC4", "neural_gain": 2},
        {"intervention": "SILENCE_LC4", "max_steps": 201},
        {"intervention": "SILENCE_LC4", "seed": -1},
        {"intervention": "SILENCE_LC4", "world": {"start_distance": 0}},
        {"intervention": "SILENCE_LC4", "world": {"object_size": 3}},
    ],
)
def test_invalid_interventions_and_parameters_are_rejected(client: TestClient, body) -> None:
    response = client.post("/embodiment/intervention/compare", json=body)
    assert response.status_code == 422, response.text


# ----------------------------------------------------------------------------- 13 failures
def test_trial_failure_produces_no_comparison(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = client.app.state.escape.get().experiment
    original = experiment.run
    calls = {"n": 0}

    def explode(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 35:  # control finishes (30 calls); the intervention trial fails
            raise NumericalInstabilityError("membrane potential became NaN")
        return original(*args, **kwargs)

    monkeypatch.setattr(experiment, "run", explode)
    response = client.post("/embodiment/intervention/compare", json={"intervention": "SILENCE_LC4"})
    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"]["error"] == "simulation_error"
    assert (
        "comparison" not in payload and "control" not in payload and "intervention" not in payload
    )
    monkeypatch.undo()
    assert compare(client, "SILENCE_LC4", max_steps=3)["comparison"]["matched_conditions"][
        "all_matched"
    ]


def test_missing_circuit_yields_503_without_a_comparison(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for response in (
            client.get("/embodiment/intervention/config"),
            client.post("/embodiment/intervention/compare", json={"intervention": "SILENCE_LC4"}),
        ):
            assert response.status_code == 503
            assert response.json()["detail"]["error"] == "circuit_unavailable"
            assert "comparison" not in response.json()


def test_p5_p6_p7_1_endpoints_unchanged(client: TestClient) -> None:
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/embodiment/intervention/config", "/embodiment/intervention/compare"} <= paths
    assert {"/embodiment/config", "/embodiment/run", "/escape/config", "/escape/run"} <= paths
    assert {"/circuits", "/circuits/{circuit_id}/provenance"} <= paths
    escape = client.post(
        "/escape/run", json={"stimulus": "looming", "direction": "center", "intensity": 0.5}
    ).json()
    assert escape["action"] == "ESCAPE"
    assert "intervention" not in escape  # the P5 response model is unchanged
    cfg = client.get("/embodiment/config").json()
    assert cfg["experiment_name"] == "virtual_threat_lab_v1"
