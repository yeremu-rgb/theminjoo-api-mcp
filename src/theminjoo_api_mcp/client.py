import asyncio
import time
from typing import Any

import httpx

from .config import Settings, settings
from .models import Board, PostDetail, PostSummary
from .parser import parse_detail, parse_list


class TTLCache:
    def __init__(self, ttl: int):
        self.ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        expires, value = item
        if expires <= time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic() + self.ttl, value)


class TheMinjooClient:
    def __init__(self, cfg: Settings = settings, transport: httpx.AsyncBaseTransport | None = None):
        self.cfg = cfg
        self.cache = TTLCache(cfg.cache_ttl_seconds)
        self._client = httpx.AsyncClient(
            timeout=cfg.request_timeout,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": cfg.user_agent, "Accept-Language": "ko-KR,ko;q=0.9"},
        )
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict[str, Any]) -> str:
        key = f"{url}?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            self.cache.set(key, response.text)
            return response.text

    async def list_posts(self, board: Board, offset: int = 0, limit: int = 20) -> list[PostSummary]:
        html = await self._get(f"{self.cfg.base_url}/list.php", {"brd": int(board), "sno": offset})
        return parse_list(html, board, self.cfg.base_url)[:limit]

    async def get_post(self, board: Board, post_id: int) -> PostDetail:
        url = f"{self.cfg.base_url}/view.php?brd={int(board)}&post={post_id}"
        html = await self._get(
            f"{self.cfg.base_url}/view.php", {"brd": int(board), "post": post_id}
        )
        return parse_detail(html, board, post_id, url)

    async def search(
        self, board: Board, query: str, pages: int = 3, page_size: int = 20
    ) -> list[PostSummary]:
        query_folded = query.casefold().strip()
        results: list[PostSummary] = []
        for page in range(max(1, min(pages, 10))):
            posts = await self.list_posts(board, offset=page * page_size, limit=page_size)
            results.extend(p for p in posts if query_folded in p.title.casefold())
            if len(posts) < page_size:
                break
        return results
