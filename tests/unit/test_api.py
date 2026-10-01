from fastapi.testclient import TestClient

from agent_platform.api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_endpoint_requires_authentication() -> None:
    response = TestClient(app).post("/v1/agents/run", json={"message": "hello"})
    assert response.status_code == 401
