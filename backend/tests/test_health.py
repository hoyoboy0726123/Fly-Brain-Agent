from fastapi.testclient import TestClient

from app import CURRENT_PHASE, SERVICE_NAME, __version__
from app.models import HealthResponse


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_health_payload_matches_schema(client: TestClient) -> None:
    payload = client.get("/health").json()
    parsed = HealthResponse.model_validate(payload)
    assert parsed.status == "ok"
    assert parsed.service == SERVICE_NAME
    assert parsed.version == __version__
    assert parsed.phase == CURRENT_PHASE


def test_health_reports_injected_environment(client: TestClient) -> None:
    assert client.get("/health").json()["environment"] == "test"


def test_health_has_no_unexpected_fields(client: TestClient) -> None:
    assert set(client.get("/health").json()) == {
        "status",
        "service",
        "version",
        "environment",
        "phase",
    }


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/does-not-exist").status_code == 404
