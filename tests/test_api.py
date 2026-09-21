import base64
import hashlib

import pytest
from fastapi.testclient import TestClient

from theminjoo_api_mcp.api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_advertises_remote_mcp(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["mcp"] == "/mcp"
    assert response.json()["oauth_metadata"] == "/.well-known/oauth-authorization-server"


def test_boards(client):
    response = client.get("/v1/boards")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {11, 230}


def test_remote_mcp_is_mounted():
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_oauth_discovery_metadata(client):
    protected = client.get("/.well-known/oauth-protected-resource")
    assert protected.status_code == 200
    assert protected.json()["resource"].endswith("/mcp")

    auth = client.get("/.well-known/oauth-authorization-server")
    assert auth.status_code == 200
    body = auth.json()
    assert body["authorization_endpoint"].endswith("/oauth/authorize")
    assert body["token_endpoint"].endswith("/oauth/token")
    assert body["registration_endpoint"].endswith("/oauth/register")
    assert "refresh_token" in body["grant_types_supported"]
    assert "S256" in body["code_challenge_methods_supported"]


def test_mcp_requires_oauth_and_advertises_resource_metadata(client):
    response = client.get("/mcp")
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert "resource_metadata=" in challenge
    assert "/.well-known/oauth-protected-resource" in challenge


def test_dynamic_registration_and_pkce_authorization(client):
    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    registration = client.post(
        "/oauth/register",
        json={
            "client_name": "test-mcp-client",
            "redirect_uris": ["https://client.example/callback"],
        },
    )
    assert registration.status_code == 201
    client_id = registration.json()["client_id"]
    assert client_id.startswith("dcr.")

    authorize = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp offline_access",
            "state": "abc",
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 200
    assert "연결 허용" in authorize.text
