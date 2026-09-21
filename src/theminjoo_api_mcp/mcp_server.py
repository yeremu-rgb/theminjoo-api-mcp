import asyncio

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .client import TheMinjooClient
from .models import Board

mcp = FastMCP(
    "theminjoo-api-mcp",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

client = TheMinjooClient()


def _board(value: int) -> Board:
    try:
        return Board(value)
    except ValueError as exc:
        raise ValueError("board must be 11 (논평·브리핑) or 230 (모두발언)") from exc


@mcp.tool()
async def list_posts(board: int, offset: int = 0, limit: int = 20) -> list[dict]:
    """List official 더불어민주당 posts. board: 11=논평·브리핑, 230=모두발언."""
    items = await client.list_posts(
        _board(board), offset=max(0, offset), limit=max(1, min(limit, 100))
    )
    return [item.model_dump(mode="json") for item in items]


@mcp.tool()
async def get_post(board: int, post_id: int) -> dict:
    """Get one official post including body text and metadata."""
    item = await client.get_post(_board(board), post_id)
    return item.model_dump(mode="json")


@mcp.tool()
async def search_posts(board: int, query: str, pages: int = 3) -> list[dict]:
    """Search recent post titles across up to 10 list pages."""
    items = await client.search(_board(board), query, pages=max(1, min(pages, 10)))
    return [item.model_dump(mode="json") for item in items]


def run() -> None:
    """Run the local stdio MCP server."""
    try:
        mcp.run(transport="stdio")
    finally:
        asyncio.run(client.close())


if __name__ == "__main__":
    run()
