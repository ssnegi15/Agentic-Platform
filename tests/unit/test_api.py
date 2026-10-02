from fastapi.testclient import TestClient

from agent_platform.api.main import app


def test_app_root_describes_api() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Agent Platform API"


def test_pages_origin_cors_preflight() -> None:
    response = TestClient(app).options(
        "/v1/me",
        headers={
            "Origin": "https://ssnegi15.github.io",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ssnegi15.github.io"


def test_cors_does_not_allow_other_origins() -> None:
    response = TestClient(app).options(
        "/v1/me",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_endpoint_requires_authentication() -> None:
    response = TestClient(app).post("/v1/agents/run", json={"message": "hello"})
    assert response.status_code == 401
