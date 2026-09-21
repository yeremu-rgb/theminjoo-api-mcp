from fastapi.testclient import TestClient

from theminjoo_api_mcp.api import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_root_advertises_remote_mcp():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["mcp"] == "/mcp"


def test_boards():
    with TestClient(app) as client:
        response = client.get("/v1/boards")
        assert response.status_code == 200
        assert {item["id"] for item in response.json()} == {11, 230}


def test_remote_mcp_is_mounted():
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
