import base64
import hashlib
from urllib.parse import parse_qs, urlparse

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

    protected_path = client.get("/.well-known/oauth-protected-resource/mcp")
    assert protected_path.status_code == 200

    auth = client.get("/.well-known/oauth-authorization-server")
    assert auth.status_code == 200
    body = auth.json()
    assert body["authorization_endpoint"].endswith("/authorize")
    assert body["token_endpoint"].endswith("/token")
    assert body["registration_endpoint"].endswith("/register")
    assert "refresh_token" in body["grant_types_supported"]
    assert "S256" in body["code_challenge_methods_supported"]
    assert body["authorization_response_iss_parameter_supported"] is True
    assert "offline_access" in body["scopes_supported"]

    oidc_compat = client.get("/.well-known/openid-configuration")
    assert oidc_compat.status_code == 200
    assert oidc_compat.json()["issuer"] == body["issuer"]


def test_mcp_requires_oauth_and_advertises_resource_metadata(client):
    response = client.get("/mcp")
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert "resource_metadata=" in challenge
    assert "/.well-known/oauth-protected-resource" in challenge


def test_dynamic_registration_echoes_public_client_metadata(client):
    registration = client.post(
        "/register",
        json={
            "client_name": "compat-test",
            "redirect_uris": ["https://client.example/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "application_type": "web",
            "scope": "mcp offline_access",
        },
    )
    assert registration.status_code == 201
    body = registration.json()
    assert body["client_id"].startswith("dcr.")
    assert body["application_type"] == "web"
    assert body["token_endpoint_auth_method"] == "none"
    assert body["grant_types"] == ["authorization_code", "refresh_token"]
    assert body["response_types"] == ["code"]


def test_full_oauth_pkce_flow_and_mcp_initialize(client):
    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    registration = client.post(
        "/oauth/register",
        json={
            "client_name": "integration-test",
            "redirect_uris": ["https://client.example/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "application_type": "web",
        },
    )
    assert registration.status_code == 201
    client_id = registration.json()["client_id"]

    authorize = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp offline_access",
            "resource": "http://testserver/mcp",
            "state": "abc",
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 200
    assert "연결 허용" in authorize.text

    approved = client.post(
        "/authorize",
        data={
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_challenge": challenge,
            "scope": "mcp offline_access",
            "resource": "http://testserver/mcp",
            "state": "abc",
        },
        follow_redirects=False,
    )
    assert approved.status_code == 302
    query = parse_qs(urlparse(approved.headers["location"]).query)
    assert query["state"] == ["abc"]
    assert query["iss"] == ["http://testserver"]
    code = query["code"][0]

    token = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_verifier": verifier,
            "code": code,
        },
    )
    assert token.status_code == 200
    token_body = token.json()
    assert token_body["token_type"] == "Bearer"
    assert token_body["access_token"]
    assert token_body["refresh_token"]

    initialize = client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {token_body['access_token']}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
    )
    assert initialize.status_code == 200
    mcp_body = initialize.json()
    assert mcp_body["jsonrpc"] == "2.0"
    assert mcp_body["id"] == 1
    assert mcp_body["result"]["serverInfo"]["name"] == "theminjoo-api-mcp"
