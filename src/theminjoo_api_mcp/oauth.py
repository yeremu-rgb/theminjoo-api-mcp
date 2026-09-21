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
        expected = hmac.new(settings.oauth_secret.encode(), body.encode(), hashlib.sha256).digest()
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


def issue_access_token(client_id: str, scope: str) -> tuple[str, int]:
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
            }
        ),
        ttl,
    )


def issue_refresh_token(client_id: str, scope: str) -> str:
    now = int(time.time())
    return _sign(
        {
            "typ": "refresh",
            "iat": now,
            "exp": now + 30 * 24 * 3600,
            "client_id": client_id,
            "scope": scope,
        }
    )


def verify_access_token(token: str) -> dict[str, Any]:
    return _verify(token, "access")


def _valid_redirect(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _redirect_allowed(client_id: str, redirect_uri: str) -> bool:
    if not _valid_redirect(redirect_uri):
        return False
    if not client_id.startswith("dcr."):
        return True
    try:
        payload = _verify(client_id[4:], "client")
        return redirect_uri in payload.get("redirect_uris", [])
    except HTTPException:
        return False


def _pkce_ok(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode()).digest()
    return hmac.compare_digest(_b64e(digest), challenge)


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
    origin = _origin(request)
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/oauth/authorize",
        "token_endpoint": f"{origin}/oauth/token",
        "registration_endpoint": f"{origin}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp", "offline_access"],
        "client_id_metadata_document_supported": False,
    }


@router.post("/oauth/register")
async def register_client(request: Request) -> JSONResponse:
    data = await request.json()
    redirect_uris = data.get("redirect_uris") or []
    if not redirect_uris or not all(_valid_redirect(uri) for uri in redirect_uris):
        raise HTTPException(status_code=400, detail="valid redirect_uris are required")
    now = int(time.time())
    signed = _sign(
        {
            "typ": "client",
            "iat": now,
            "exp": now + 365 * 24 * 3600,
            "redirect_uris": redirect_uris,
            "client_name": data.get("client_name", "MCP client"),
        }
    )
    return JSONResponse(
        {
            "client_id": f"dcr.{signed}",
            "client_id_issued_at": now,
            "redirect_uris": redirect_uris,
            "client_name": data.get("client_name", "MCP client"),
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        status_code=201,
    )


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
) -> HTMLResponse:
    if response_type != "code":
        raise HTTPException(status_code=400, detail="response_type must be code")
    if code_challenge_method != "S256" or not code_challenge:
        raise HTTPException(status_code=400, detail="PKCE S256 is required")
    if not _redirect_allowed(client_id, redirect_uri):
        raise HTTPException(status_code=400, detail="invalid redirect_uri")

    hidden = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "scope": scope,
        "state": state or "",
    }
    inputs = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v, quote=True)}">'
        for k, v in hidden.items()
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>theminjoo-api-mcp 연결 승인</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:620px;margin:64px auto;padding:0 20px;color:#171717}}
.card{{border:1px solid #ddd;border-radius:16px;padding:28px}}
button{{background:#111;color:#fff;border:0;border-radius:10px;padding:12px 18px;font-size:16px;cursor:pointer}}
small{{color:#666}}
</style></head><body><div class="card">
<h2>theminjoo-api-mcp 연결 승인</h2>
<p>Claude 또는 ChatGPT가 더불어민주당 공식 홈페이지의 공개 논평·브리핑 및 모두발언을 조회하도록 허용합니다.</p>
<p><small>이 OAuth 흐름은 공개 데이터 MCP 연결을 위한 동의 절차이며 사용자 신원을 확인하는 로그인 서비스가 아닙니다.</small></p>
<form method="post" action="/oauth/authorize">{inputs}<button type="submit">연결 허용</button></form>
</div></body></html>"""
    )


@router.post("/oauth/authorize")
async def authorize_post(request: Request) -> RedirectResponse:
    form = await request.form()
    client_id = str(form.get("client_id", ""))
    redirect_uri = str(form.get("redirect_uri", ""))
    challenge = str(form.get("code_challenge", ""))
    scope = str(form.get("scope", "mcp offline_access"))
    state = str(form.get("state", ""))

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
        }
    )
    params = {"code": code, "iss": _origin(request)}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode(params)}", status_code=302)


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
    elif grant_type == "refresh_token":
        refresh = str(form.get("refresh_token", ""))
        payload = _verify(refresh, "refresh")
        if client_id and client_id != payload.get("client_id"):
            raise HTTPException(status_code=400, detail="client_id mismatch")
        client_id = str(payload.get("client_id", ""))
        scope = str(payload.get("scope", "mcp offline_access"))
    else:
        raise HTTPException(status_code=400, detail="unsupported grant_type")

    access, expires_in = issue_access_token(client_id, scope)
    body = {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "scope": scope,
    }
    if "offline_access" in scope.split():
        body["refresh_token"] = issue_refresh_token(client_id, scope)
    return JSONResponse(body)
