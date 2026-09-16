"""P6 read-only circuit inspection API over the committed ``escape_v1`` artifact.

Critical invariant: every edge served by the API exists in the P2 artifact (and vice
versa); nothing is reconstructed. Fields the artifact does not carry come back ``null``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.circuits import NEIGHBORS_LABEL, SIMULATION_WEIGHT_LABEL, STRUCTURAL_LABEL
from app.behavior import DISCLAIMER, load_escape_config
from app.circuits import Circuit
from app.config import Settings
from app.main import create_app
from app.simulation.weights import normalize_weight

CONFIG = load_escape_config("escape_v1")
ARTIFACT_PATH = Settings(_env_file=None).circuits_data_dir / "escape_v1.json"
ARTIFACT = Circuit.load(ARTIFACT_PATH)
ARTIFACT_EDGES = {(e.pre_neuron_id, e.post_neuron_id, e.synapse_count) for e in ARTIFACT.edges}
BASE = "/circuits/escape_v1"


def get(client: TestClient, path: str, **params) -> dict:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def all_pages(client: TestClient, path: str, limit: int, **params) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        page = get(client, path, offset=offset, limit=limit, **params)
        items.extend(page["items"])
        if offset + limit >= page["total"]:
            return items
        offset += limit


# ----------------------------------------------------------------------------- circuit
def test_list_circuits_includes_escape_v1_with_status(client: TestClient) -> None:
    items = {c["circuit_id"]: c for c in get(client, "/circuits")}
    assert "escape_v1" in items
    assert items["escape_v1"]["neurons"] == 286 and items["escape_v1"]["edges"] == 932
    assert items["escape_v1"]["biological_status"] == "PARTIALLY SUPPORTED"
    assert items["escape_v1"]["circuit_hash"] == CONFIG.expected_circuit_hash


def test_circuit_summary(client: TestClient) -> None:
    summary = get(client, BASE)
    assert summary["circuit_id"] == "escape_v1"
    assert summary["dataset"] == "male-cns" and summary["dataset_version"] == "v1.0"
    assert summary["circuit_hash"] == ARTIFACT.compute_hash() == CONFIG.expected_circuit_hash
    assert summary["canonical_graph"]["selection_rule"] == 'status == "Traced"'
    assert summary["canonical_graph"]["neuron_count"] == 165_122
    assert summary["canonical_graph"]["connection_count"] == 25_563_197
    assert summary["neurons"] == 286 and summary["edges"] == 932
    assert summary["cell_type_counts"] == {"DNp01": 2, "LC4": 126, "LPLC2": 158}
    assert summary["synapses_total"] == sum(e.synapse_count for e in ARTIFACT.edges)
    assert summary["biological_status"] == "PARTIALLY SUPPORTED"
    assert summary["research_document"] == "docs/circuits/escape_v1.md"
    assert summary["biological_interpretation"].startswith("NONE")
    assert summary["disclaimer"] == DISCLAIMER


def test_unknown_and_unsafe_circuit_ids_are_404(client: TestClient) -> None:
    for circuit_id in ("does_not_exist", "..escape_v1", "a b", "escape_v1.json"):
        response = client.get(f"/circuits/{circuit_id}")
        assert response.status_code == 404, circuit_id
        assert response.json()["detail"]["error"] == "circuit_not_found"
    assert client.get("/circuits/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_tampered_artifact_is_reported_as_mismatch(tmp_path: Path) -> None:
    payload = json.loads(ARTIFACT_PATH.read_text())
    payload["edges"][0]["synapse_count"] += 1  # structure changed, hash no longer matches
    circuits_dir = tmp_path / "circuits"
    circuits_dir.mkdir()
    (circuits_dir / "escape_v1.json").write_text(json.dumps(payload))
    settings = Settings(_env_file=None, environment="test", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get(BASE)
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "circuit_mismatch"


# ----------------------------------------------------------------------------- nodes
def test_nodes_are_exactly_the_artifact_nodes(client: TestClient) -> None:
    page = get(client, f"{BASE}/nodes")
    assert page["total"] == 286 and len(page["items"]) == 286
    assert page["circuit_hash"] == CONFIG.expected_circuit_hash
    assert {n["neuron_id"] for n in page["items"]} == {n.neuron_id for n in ARTIFACT.nodes}
    by_id = {n.neuron_id: n for n in ARTIFACT.nodes}
    for item in page["items"]:
        node = by_id[item["neuron_id"]]
        assert item["cell_type"] == node.cell_type
        assert item["cell_class"] == node.cell_class  # None → "Not available" in the UI
        assert item["neurotransmitter_prediction"] == node.neurotransmitter
        assert item["minimum_hop_from_seed"] == node.minimum_hop_from_seed
        assert item["is_seed"] == node.is_seed and item["is_target"] == node.is_target
        assert item["dataset"] == "male-cns" and item["dataset_version"] == "v1.0"


def test_nodes_pagination_and_filters(client: TestClient) -> None:
    pages = all_pages(client, f"{BASE}/nodes", limit=100)
    assert len(pages) == 286 and len({n["neuron_id"] for n in pages}) == 286
    page = get(client, f"{BASE}/nodes", offset=280, limit=100)
    assert page["total"] == 286 and len(page["items"]) == 6
    lc4 = get(client, f"{BASE}/nodes", cell_type="LC4")
    assert lc4["total"] == 126 and all(n["cell_type"] == "LC4" for n in lc4["items"])
    gf = get(client, f"{BASE}/nodes", cell_type="DNp01")
    assert {n["neuron_id"]: (n["side"], n["role"]) for n in gf["items"]} == {
        "10010": ("L", "output"),
        "10001": ("R", "output"),
    }
    exact = get(client, f"{BASE}/nodes", search="10010")
    assert exact["total"] == 1 and exact["items"][0]["is_target"] is True
    assert get(client, f"{BASE}/nodes", search="1001")["total"] == 0  # exact match only
    assert get(client, f"{BASE}/nodes", search="no-such-id")["total"] == 0
    prefix = get(client, f"{BASE}/nodes", id_prefix="1001")
    assert prefix["total"] >= 2 and all(n["neuron_id"].startswith("1001") for n in prefix["items"])
    assert client.get(f"{BASE}/nodes", params={"limit": 0}).status_code == 422
    assert client.get(f"{BASE}/nodes", params={"limit": 5000}).status_code == 422


def test_node_degrees_are_computed_from_artifact_edges(client: TestClient) -> None:
    gf_left = next(
        n
        for n in get(client, f"{BASE}/nodes", cell_type="DNp01")["items"]
        if n["neuron_id"] == "10010"
    )
    incoming = [e for e in ARTIFACT.edges if e.post_neuron_id == "10010"]
    assert gf_left["in_degree"] == len(incoming) == 155
    assert gf_left["in_synapses"] == sum(e.synapse_count for e in incoming)
    assert gf_left["out_degree"] == 0 and gf_left["out_synapses"] == 0


# ----------------------------------------------------------------------------- edges
def test_every_served_edge_exists_in_the_artifact_and_vice_versa(client: TestClient) -> None:
    served = all_pages(client, f"{BASE}/edges", limit=250)
    assert len(served) == 932
    served_set = {(e["pre_neuron_id"], e["post_neuron_id"], e["synapse_count"]) for e in served}
    assert served_set == ARTIFACT_EDGES
    assert all(e["dataset"] == "male-cns" and e["dataset_version"] == "v1.0" for e in served)
    assert all(e["label"] == STRUCTURAL_LABEL for e in served)
    assert all(e["simulation_weight"] is None for e in served)


def test_edges_filters_and_pagination(client: TestClient) -> None:
    page = get(client, f"{BASE}/edges", offset=900, limit=100)
    assert page["total"] == 932 and len(page["items"]) == 32
    onto_gf = get(client, f"{BASE}/edges", post="10010")
    assert onto_gf["total"] == 155
    from_lc4 = get(client, f"{BASE}/edges", pre="12032")
    assert {e["post_neuron_id"] for e in from_lc4["items"]} == {
        e.post_neuron_id for e in ARTIFACT.edges if e.pre_neuron_id == "12032"
    }
    strong = get(client, f"{BASE}/edges", min_synapses=80)
    assert all(e["synapse_count"] >= 80 for e in strong["items"])
    assert strong["total"] == sum(1 for e in ARTIFACT.edges if e.synapse_count >= 80)


def test_simulation_weight_is_optional_and_labelled_computational(client: TestClient) -> None:
    page = get(client, f"{BASE}/edges", limit=3, include_simulation_weight="true")
    for edge in page["items"]:
        weight = edge["simulation_weight"]
        assert weight["label"] == SIMULATION_WEIGHT_LABEL
        assert "not a biological synaptic strength" in weight["label"]
        assert "NOT MEASURED" in weight["parameter_label"]
        assert weight["weight_transform"] == "log1p" and weight["weight_scale"] == 1.0
        assert weight["value"] == pytest.approx(
            normalize_weight(edge["synapse_count"], "log1p", 1.0)
        )
        assert "Biological structural observation" in edge["synapse_count_label"]


def test_edge_detail_and_missing_edge(client: TestClient) -> None:
    detail = get(client, f"{BASE}/edges/12032/10010")
    assert detail["label"] == "BIOLOGICAL STRUCTURAL CONNECTION"
    assert detail["pre"]["neuron_id"] == "12032" and detail["pre"]["cell_type"] == "LC4"
    assert detail["post"]["neuron_id"] == "10010" and detail["post"]["cell_type"] == "DNp01"
    artifact_edge = next(
        e for e in ARTIFACT.edges if (e.pre_neuron_id, e.post_neuron_id) == ("12032", "10010")
    )
    assert detail["synapse_count"] == artifact_edge.synapse_count
    assert detail["circuit_id"] == "escape_v1"
    assert detail["circuit_hash"] == CONFIG.expected_circuit_hash
    assert detail["simulation_weight"]["value"] == pytest.approx(
        normalize_weight(artifact_edge.synapse_count, "log1p", 1.0)
    )
    response = client.get(f"{BASE}/edges/10010/12032")  # GF → LC4 does not exist
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "edge_not_found"


# ----------------------------------------------------------------------------- neurons
def test_neuron_lookup_separates_biological_and_circuit_metadata(client: TestClient) -> None:
    detail = get(client, f"{BASE}/neurons/10010")
    bio = detail["biological"]
    assert bio["label"].startswith("BIOLOGICAL METADATA")
    assert bio["neuron_id"] == "10010" and bio["cell_type"] == "DNp01"
    assert bio["cell_class"] is None  # not in the artifact → "Not available" in the UI
    assert bio["neurotransmitter_prediction"] == "acetylcholine"
    assert bio["dataset"] == "male-cns" and bio["dataset_version"] == "v1.0"
    circuit = detail["circuit"]
    assert circuit["label"].startswith("CIRCUIT / SIMULATION METADATA")
    assert circuit["minimum_hop_from_seed"] == 1
    assert circuit["is_seed"] is False and circuit["is_target"] is True
    assert circuit["side"] == "L" and circuit["role"] == "output"
    assert circuit["stimulated_by_config"] is False
    assert detail["connectivity"]["label"] == NEIGHBORS_LABEL
    assert detail["connectivity"]["in_degree"] == 155
    assert detail["not_available_marker"] == "Not available"
    assert set(bio) == {
        "label",
        "neuron_id",
        "cell_type",
        "cell_class",
        "neurotransmitter_prediction",
        "dataset",
        "dataset_version",
    }


def test_seed_neuron_lookup(client: TestClient) -> None:
    detail = get(client, f"{BASE}/neurons/12032")
    assert detail["biological"]["cell_type"] == "LC4"
    assert detail["circuit"]["is_seed"] is True and detail["circuit"]["is_target"] is False
    assert detail["circuit"]["minimum_hop_from_seed"] == 0
    assert detail["circuit"]["side"] == "L" and detail["circuit"]["role"] == "sensory"
    assert detail["circuit"]["stimulated_by_config"] is True


def test_missing_neuron_is_404(client: TestClient) -> None:
    response = client.get(f"{BASE}/neurons/999999")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "neuron_not_found"
    assert client.get(f"{BASE}/neurons/999999/neighbors").status_code == 404


# ----------------------------------------------------------------------------- neighbors
def test_neighbors_are_within_the_loaded_circuit_only(client: TestClient) -> None:
    payload = get(client, f"{BASE}/neurons/10010/neighbors")
    assert payload["label"] == NEIGHBORS_LABEL
    upstream = payload["upstream"]
    assert upstream["total"] == 155 and payload["downstream"]["total"] == 0
    ids = {row["neuron_id"] for row in upstream["items"]}
    assert ids == {e.pre_neuron_id for e in ARTIFACT.edges if e.post_neuron_id == "10010"}
    assert {row["cell_type"] for row in upstream["items"]} == {"LC4", "LPLC2"}
    synapses = [row["synapse_count"] for row in upstream["items"]]
    assert synapses == sorted(synapses, reverse=True)
    for row in upstream["items"]:
        assert (row["pre_neuron_id"], row["post_neuron_id"], row["synapse_count"]) in ARTIFACT_EDGES


def test_neighbors_direction_and_pagination(client: TestClient) -> None:
    only_up = get(client, f"{BASE}/neurons/12032/neighbors", direction="upstream")
    assert only_up["downstream"] is None and only_up["upstream"]["total"] == 1
    only_down = get(client, f"{BASE}/neurons/12032/neighbors", direction="downstream")
    assert only_down["upstream"] is None
    assert {r["neuron_id"] for r in only_down["downstream"]["items"]} == {
        e.post_neuron_id for e in ARTIFACT.edges if e.pre_neuron_id == "12032"
    }
    page = get(client, f"{BASE}/neurons/10010/neighbors", offset=150, limit=10)
    assert page["upstream"]["total"] == 155 and len(page["upstream"]["items"]) == 5
    assert (
        client.get(f"{BASE}/neurons/10010/neighbors", params={"direction": "sideways"}).status_code
        == 422
    )


# ----------------------------------------------------------------------------- provenance
def test_provenance_panel_facts(client: TestClient) -> None:
    prov = get(client, f"{BASE}/provenance")
    assert prov["disclaimer"] == DISCLAIMER
    assert prov["circuit_id"] == "escape_v1"
    assert prov["circuit_hash"] == prov["expected_circuit_hash"] == CONFIG.expected_circuit_hash
    assert prov["circuit_verified"] is True
    assert prov["biological_status"] == "PARTIALLY SUPPORTED"
    assert prov["dataset"] == "male-cns" and prov["dataset_version"] == "v1.0"
    assert prov["source_dataset"]["name"] == "MaleCNS"
    assert prov["source_dataset"]["official_neuron_count"] == 166_700
    assert prov["canonical_graph"]["selection_rule"] == 'status == "Traced"'
    assert prov["canonical_graph"]["neuron_count"] == 165_122
    assert prov["canonical_graph"]["connection_count"] == 25_563_197
    assert "NOT the complete" in prov["canonical_graph_note"]
    assert prov["loaded_circuit"] == {"neurons": 286, "edges": 932}
    assert prov["license"].startswith("CC-BY 4.0")
    assert prov["source_page"] == "https://male-cns.janelia.org/download/"
    assert prov["download_url"].startswith("gs://flyem-male-cns/v1.0/")
    assert {f["role"] for f in prov["raw_files"]} == {"annotations", "weights", "neurotransmitters"}
    assert all(len(f["sha256"]) == 64 for f in prov["raw_files"])
    assert len(prov["citations"]) == 7
    assert {c["key"] for c in prov["citations"]} >= {"klapoetke2017", "namiki2018", "jang2023"}
    assert prov["mapping_confidence"] and prov["limitations"]


def test_synthetic_fixture_circuit_has_no_biological_status(client: TestClient) -> None:
    prov = get(client, "/circuits/fixture_smoke_downstream/provenance")
    assert prov["biological_status"] is None and prov["citations"] == []
    assert prov["dataset"] == "synthetic_tiny_connectome"
    summary = get(client, "/circuits/fixture_smoke_downstream")
    assert summary["neurons"] == 6 and summary["edges"] == 9


# ----------------------------------------------------------------------------- activity replay data
def test_run_response_carries_per_neuron_simulated_state(client: TestClient) -> None:
    response = client.post("/escape/run", json={"direction": "center", "intensity": 0.5})
    assert response.status_code == 200
    payload = response.json()
    activity = payload["neuron_activity"]
    assert "SIMULATED STATE" in activity["label"] and "not measured" in activity["label"]
    n = len(activity["neuron_ids"])
    assert n == 286 and set(activity["neuron_ids"]) == {x.neuron_id for x in ARTIFACT.nodes}
    steps = payload["steps"]
    assert len(activity["membrane_potential_per_step"]) == steps
    assert len(activity["refractory_per_step"]) == steps
    assert all(len(row) == n for row in activity["membrane_potential_per_step"])
    assert all(len(row) == n for row in activity["refractory_per_step"])
    fired_counts = [len(ids) for ids in activity["fired_ids_per_step"]]
    assert fired_counts == payload["per_step_fired_counts"]
    gf = activity["neuron_ids"].index("10010")
    assert "10010" in activity["fired_ids_per_step"][3]  # GF L fires at step 4
    assert activity["refractory_per_step"][3][gf] == 2
    assert activity["membrane_potential_per_step"][3][gf] == activity["reset_potential"]
    assert activity["threshold"] == 1.0
    assert all(abs(v) < 1e6 for row in activity["membrane_potential_per_step"] for v in row)


def test_no_endpoint_serves_the_canonical_graph(client: TestClient) -> None:
    assert get(client, f"{BASE}/nodes")["total"] == 286 < 165_122
    assert get(client, f"{BASE}/edges")["total"] == 932 < 25_563_197
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/circuits",
        "/circuits/{circuit_id}",
        "/circuits/{circuit_id}/provenance",
        "/circuits/{circuit_id}/nodes",
        "/circuits/{circuit_id}/edges",
        "/circuits/{circuit_id}/edges/{pre_neuron_id}/{post_neuron_id}",
        "/circuits/{circuit_id}/neurons/{neuron_id}",
        "/circuits/{circuit_id}/neurons/{neuron_id}/neighbors",
    ):
        assert path in paths
