from fastapi.testclient import TestClient

from app import __version__
from app.config import Settings
from app.main import create_app


def test_create_app_uses_settings(test_settings: Settings) -> None:
    application = create_app(test_settings)
    assert application.title == test_settings.app_name
    assert application.version == __version__


def test_openapi_documents_health(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]


def test_cors_allows_configured_origin(client: TestClient) -> None:
    origin = "http://localhost:5173"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_for_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_custom_cors_origins_are_honoured() -> None:
    settings = Settings(_env_file=None, environment="test", cors_origins="http://demo.example")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "http://demo.example"})
        assert response.headers.get("access-control-allow-origin") == "http://demo.example"
