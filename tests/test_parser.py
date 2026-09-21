from pathlib import Path

from theminjoo_api_mcp.models import Board
from theminjoo_api_mcp.parser import parse_detail, parse_list

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://theminjoo.kr/main/sub/news"


def test_parse_list():
    html = (FIXTURES / "list.html").read_text()
    items = parse_list(html, Board.BRIEFINGS, BASE)
    assert len(items) == 2
    assert items[0].post_id == 1219999
    assert items[0].category == "서면브리핑"
    assert items[0].published_at.date().isoformat() == "2026-09-21"


def test_parse_detail():
    html = (FIXTURES / "detail.html").read_text()
    item = parse_detail(
        html,
        Board.BRIEFINGS,
        1219999,
        f"{BASE}/view.php?brd=11&post=1219999",
    )
    assert item.title.startswith("[홍길동")
    assert item.author == "더불어민주당 공보국"
    assert item.views == 1234
    assert "두 번째 문단" in item.content
    assert len(item.attachments) == 1
