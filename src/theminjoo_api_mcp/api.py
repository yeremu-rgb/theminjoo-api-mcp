from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from . import __version__
from .client import TheMinjooClient
from .config import settings
from .mcp_server import client as mcp_client
from .mcp_server import mcp
from .models import Board, PostDetail, PostList, PostSummary
from .oauth import router as oauth_router
from .oauth import verify_access_token

client = TheMinjooClient()


class OAuthBearerMiddleware:
    """Protect remote MCP with OAuth bearer tokens and optional legacy static token."""

    def __init__(self, app):
        self.app = app

    def _origin(self, scope) -> str:
        if settings.public_url:
            return settings.public_url.rstrip("/")
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        host = headers.get("host", "localhost")
        scheme = scope.get("scheme", "https")
        return f"{scheme}://{host}"

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") != "OPTIONS":
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            auth = headers.get("authorization", "")
            valid = False

            if settings.mcp_token and auth == f"Bearer {settings.mcp_token}":
                valid = True
            elif auth.startswith("Bearer "):
                try:
                    verify_access_token(auth[7:])
                    valid = True
                except HTTPException:
                    valid = False

            if not valid:
                origin = self._origin(scope)
                response = JSONResponse(
                    {
                        "error": "invalid_token",
                        "error_description": "OAuth authorization is required for this MCP endpoint.",
                    },
                    status_code=401,
                    headers={
                        "WWW-Authenticate": (
                            'Bearer scope="mcp", '
                            f'resource_metadata="{origin}/.well-known/oauth-protected-resource"'
                        )
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        try:
            yield
        finally:
            await client.close()
            await mcp_client.close()


app = FastAPI(
    title="theminjoo-api-mcp",
    version=__version__,
    description="Unofficial API for 더불어민주당 논평·브리핑 and 모두발언.",
    lifespan=lifespan,
)
app.include_router(oauth_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "theminjoo-api-mcp",
        "version": __version__,
        "rest_docs": "/docs",
        "mcp": "/mcp",
        "oauth_metadata": "/.well-known/oauth-authorization-server",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/boards")
async def boards() -> list[dict[str, int | str]]:
    return [{"id": int(board), "label": board.label} for board in Board]


@app.get("/v1/posts", response_model=PostList)
async def list_posts(
    board: Annotated[Board, Query(description="11=논평·브리핑, 230=모두발언")],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
) -> PostList:
    try:
        items = await client.list_posts(board, offset=offset, limit=limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc
    return PostList(
        items=items,
        board=board,
        offset=offset,
        limit=limit,
        next_offset=offset + len(items) if len(items) == limit else None,
    )


@app.get("/v1/posts/{board}/{post_id}", response_model=PostDetail)
async def get_post(board: Board, post_id: int) -> PostDetail:
    try:
        return await client.get_post(board, post_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="post not found") from exc
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc


@app.get("/v1/search", response_model=list[PostSummary])
async def search_posts(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    board: Board,
    pages: Annotated[int, Query(ge=1, le=10)] = 3,
) -> list[PostSummary]:
    try:
        return await client.search(board, q, pages=pages)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc


remote_mcp_app = mcp.streamable_http_app()
remote_mcp_app = CORSMiddleware(
    remote_mcp_app,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "Last-Event-ID",
        "Mcp-Protocol-Version",
        "Mcp-Session-Id",
    ],
    expose_headers=["Mcp-Session-Id", "WWW-Authenticate"],
)
remote_mcp_app = OAuthBearerMiddleware(remote_mcp_app)
app.mount("/mcp", remote_mcp_app)
