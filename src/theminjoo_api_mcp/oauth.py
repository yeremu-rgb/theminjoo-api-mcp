import base64
import hashlib
import hmac
import html
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .config import settings

router = APIRouter()
_USED_CODES: set[str] = set()


def _origin(request: Request) -> str:
    if settings.public_url:
        return settings.public_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def _resource(request: Request) -> str:
    return f"{_origin(request)}/mcp"


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: dict[str, Any]) -> str:
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(settings.oauth_secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def _verify(token: str, expected_type: str) -> dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            settings.oauth_secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64d(sig), expected):
            raise ValueError("bad signature")
        payload = json.loads(_b64d(body))
        if payload.get("typ") != expected_type:
            raise ValueError("bad token type")
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


def issue_access_token(
    client_id: str,
    scope: str,
    resource: str,
) -> tuple[str, int]:
    now = int(time.time())
    ttl = 3600
    return (
        _sign(
            {
                "typ": "access",
                "iat": now,
                "exp": now + ttl,
                "client_id": client_id,
                "scope": scope,
                "resource": resource,
            }
        ),
        ttl,
    )


def issue_refresh_token(client_id: str, scope: str, resource: str) -> str:
    now = int(time.time())
    return _sign(
        {
            "typ": "refresh",
            "iat": now,
            "exp": now + 30 * 24 * 3600,
            "client_id": client_id,
            "scope": scope,
            "resource": resource,
        }
    )


def verify_access_token(token: str, resource: str | None = None) -> dict[str, Any]:
    payload = _verify(token, "access")
    if resource and payload.get("resource") != resource:
        raise HTTPException(status_code=401, detail="token resource mismatch")
    return payload


def _valid_redirect(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    return parsed.scheme == "http" and parsed.hostname in local_hosts


def _client_metadata(client_id: str) -> dict[str, Any]:
    if not client_id.startswith("dcr."):
        raise HTTPException(status_code=400, detail="unknown client_id")
    return _verify(client_id[4:], "client")


def _redirect_allowed(client_id: str, redirect_uri: str) -> bool:
    if not _valid_redirect(redirect_uri):
        return False
    try:
        payload = _client_metadata(client_id)
    except HTTPException:
        return False
    return redirect_uri in payload.get("redirect_uris", [])


def _pkce_ok(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode()).digest()
    return hmac.compare_digest(_b64e(digest), challenge)


def _metadata(origin: str) -> dict[str, Any]:
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/authorize",
        "token_endpoint": f"{origin}/token",
        "registration_endpoint": f"{origin}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp", "offline_access"],
        "authorization_response_iss_parameter_supported": True,
        "client_id_metadata_document_supported": False,
    }


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata(request: Request) -> dict[str, Any]:
    origin = _origin(request)
    return {
        "resource": f"{origin}/mcp",
        "authorization_servers": [origin],
        "scopes_supported": ["mcp", "offline_access"],
        "bearer_methods_supported": ["header"],
        "resource_name": "theminjoo-api-mcp",
    }


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(request: Request) -> dict[str, Any]:
    return _metadata(_origin(request))


@router.get("/.well-known/openid-configuration")
async def openid_compatibility_metadata(request: Request) -> dict[str, Any]:
    return _metadata(_origin(request))


def _registration_response(data: dict[str, Any]) -> dict[str, Any]:
    redirect_uris = data.get("redirect_uris") or []
    if not redirect_uris or not all(_valid_redirect(uri) for uri in redirect_uris):
        raise HTTPException(status_code=400, detail="valid redirect_uris are required")

    token_method = data.get("token_endpoint_auth_method", "none")
    if token_method != "none":
        raise HTTPException(
            status_code=400,
            detail="only token_endpoint_auth_method=none is supported",
        )

    grant_types = data.get("grant_types") or ["authorization_code", "refresh_token"]
    if "authorization_code" not in grant_types:
        raise HTTPException(status_code=400, detail="authorization_code grant is required")

    response_types = data.get("response_types") or ["code"]
    if response_types != ["code"]:
        raise HTTPException(status_code=400, detail="response_types must contain only code")

    application_type = data.get("application_type")
    if application_type not in {None, "web", "native"}:
        raise HTTPException(status_code=400, detail="invalid application_type")

    now = int(time.time())
    client_record = {
        "typ": "client",
        "iat": now,
        "exp": now + 10 * 365 * 24 * 3600,
        "redirect_uris": redirect_uris,
        "client_name": data.get("client_name", "MCP client"),
        "application_type": application_type,
    }
    signed = _sign(client_record)

    response: dict[str, Any] = {
        "client_id": f"dcr.{signed}",
        "client_id_issued_at": now,
        "redirect_uris": redirect_uris,
        "client_name": data.get("client_name", "MCP client"),
        "grant_types": grant_types,
        "response_types": response_types,
        "token_endpoint_auth_method": "none",
    }

    for key in (
        "application_type",
        "scope",
        "client_uri",
        "logo_uri",
        "policy_uri",
        "tos_uri",
        "jwks_uri",
        "software_id",
        "software_version",
        "contacts",
    ):
        if key in data:
            response[key] = data[key]

    return response


@router.post("/register")
@router.post("/oauth/register")
async def register_client(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON registration body") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="registration body must be an object")
    return JSONResponse(_registration_response(data), status_code=201)


@router.get("/authorize", response_class=HTMLResponse)
@router.get("/oauth/authorize", response_class=HTMLResponse)
async def authorize_get(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    scope: str = "mcp offline_access",
    state: str | None = None,
    resource: str | None = None,
) -> HTMLResponse:
    if response_type != "code":
        raise HTTPException(status_code=400, detail="response_type must be code")
    if code_challenge_method != "S256" or not code_challenge:
        raise HTTPException(status_code=400, detail="PKCE S256 is required")
    if not _redirect_allowed(client_id, redirect_uri):
        raise HTTPException(status_code=400, detail="invalid redirect_uri")

    resource = resource or _resource(request)
    hidden = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "scope": scope,
        "state": state or "",
        "resource": resource,
    }
    inputs = "".join(
        (
            f'<input type="hidden" name="{html.escape(k)}" '
            f'value="{html.escape(v, quote=True)}">'
        )
        for k, v in hidden.items()
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>theminjoo-api-mcp 연결 승인</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 620px;
  margin: 64px auto;
  padding: 0 20px;
  color: #171717;
}}
.card {{
  border: 1px solid #ddd;
  border-radius: 16px;
  padding: 28px;
}}
button {{
  background: #111;
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 12px 18px;
  font-size: 16px;
  cursor: pointer;
}}
small {{ color: #666; }}
</style>
</head>
<body>
<div class="card">
<h2>theminjoo-api-mcp 연결 승인</h2>
<p>Claude 또는 ChatGPT가 공개 게시물 조회 MCP 도구를 사용하도록 허용합니다.</p>
<p>
<small>
이 승인 화면은 공개 데이터 MCP 연결을 위한 OAuth 동의 절차입니다.
별도의 사용자 계정 로그인이나 개인정보 인증은 수행하지 않습니다.
</small>
</p>
<form method="post" action="/authorize">
{inputs}
<button type="submit">연결 허용</button>
</form>
</div>
</body>
</html>"""
    )


@router.post("/authorize")
@router.post("/oauth/authorize")
async def authorize_post(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = str(form.get("client_id", ""))
    redirect_uri = str(form.get("redirect_uri", ""))
    challenge = str(form.get("code_challenge", ""))
    scope = str(form.get("scope", "mcp offline_access"))
    state = str(form.get("state", ""))
    resource = str(form.get("resource", "")) or _resource(request)

    if not _redirect_allowed(client_id, redirect_uri) or not challenge:
        raise HTTPException(status_code=400, detail="invalid authorization request")

    now = int(time.time())
    code = _sign(
        {
            "typ": "code",
            "iat": now,
            "exp": now + 300,
            "jti": secrets.token_urlsafe(12),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "scope": scope,
            "resource": resource,
        }
    )
    params = {"code": code, "iss": _origin(request)}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode(params)}", status_code=302)


@router.post("/token")
@router.post("/oauth/token")
async def token(request: Request) -> JSONResponse:
    form = await request.form()
    grant_type = str(form.get("grant_type", ""))
    client_id = str(form.get("client_id", ""))

    if grant_type == "authorization_code":
        code = str(form.get("code", ""))
        redirect_uri = str(form.get("redirect_uri", ""))
        verifier = str(form.get("code_verifier", ""))
        payload = _verify(code, "code")
        jti = str(payload.get("jti", ""))
        if jti in _USED_CODES:
            raise HTTPException(status_code=400, detail="authorization code already used")
        if client_id and client_id != payload.get("client_id"):
            raise HTTPException(status_code=400, detail="client_id mismatch")
        client_id = str(payload.get("client_id", ""))
        if redirect_uri != payload.get("redirect_uri"):
            raise HTTPException(status_code=400, detail="redirect_uri mismatch")
        if not _pkce_ok(verifier, str(payload.get("code_challenge", ""))):
            raise HTTPException(status_code=400, detail="invalid code_verifier")
        _USED_CODES.add(jti)
        scope = str(payload.get("scope", "mcp offline_access"))
        resource = str(payload.get("resource", _resource(request)))
    elif grant_type == "refresh_token":
        refresh = str(form.get("refresh_token", ""))
        payload = _verify(refresh, "refresh")
        if client_id and client_id != payload.get("client_id"):
            raise HTTPException(status_code=400, detail="client_id mismatch")
        client_id = str(payload.get("client_id", ""))
        scope = str(payload.get("scope", "mcp offline_access"))
        resource = str(payload.get("resource", _resource(request)))
    else:
        raise HTTPException(status_code=400, detail="unsupported grant_type")

    access, expires_in = issue_access_token(client_id, scope, resource)
    body = {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "scope": scope,
    }
    if "offline_access" in scope.split():
        body["refresh_token"] = issue_refresh_token(client_id, scope, resource)
    return JSONResponse(body)
