from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query

from . import __version__
from .client import TheMinjooClient
from .config import settings
from .models import Board, PostDetail, PostList, PostSummary

client = TheMinjooClient()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await client.close()


app = FastAPI(
    title="theminjoo-api-mcp",
    version=__version__,
    description="Unofficial API for 더불어민주당 논평·브리핑 and 모두발언.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/boards")
async def boards() -> list[dict[str, int | str]]:
    return [{"id": int(board), "label": board.label} for board in Board]


@app.get("/v1/posts", response_model=PostList)
async def list_posts(
    board: Board = Query(..., description="11=논평·브리핑, 230=모두발언"),
    offset: int = Query(0, ge=0),
    limit: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
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
    q: str = Query(..., min_length=1, max_length=200),
    board: Board = Query(...),
    pages: int = Query(3, ge=1, le=10),
) -> list[PostSummary]:
    try:
        return await client.search(board, q, pages=pages)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc
