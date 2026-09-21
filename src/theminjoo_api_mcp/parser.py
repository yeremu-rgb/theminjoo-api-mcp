import re
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .models import Board, PostDetail, PostSummary

_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?")
_VIEWS_RE = re.compile(r"조회수\s*[:：]?\s*([\d,]+)")
_AUTHOR_RE = re.compile(r"게시자\s*[:：]?\s*([^\n|]+)")


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _post_id(href: str) -> int | None:
    qs = parse_qs(urlparse(href).query)
    value = qs.get("post", [None])[0]
    return int(value) if value and value.isdigit() else None


def _parse_dt(text: str) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    date, time = match.groups()
    time = time or "00:00:00"
    if len(time) == 5:
        time += ":00"
    return datetime.fromisoformat(f"{date} {time}")


def parse_list(html: str, board: Board, base_url: str) -> list[PostSummary]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[PostSummary] = []
    seen: set[int] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if "view.php" not in href or f"brd={int(board)}" not in href:
            continue
        pid = _post_id(href)
        if pid is None or pid in seen:
            continue
        title = _clean(anchor.get_text(" ", strip=True))
        if not title or title in {"이전 글", "다음 글", "자세히보기"}:
            continue

        container: Tag = anchor
        for parent in anchor.parents:
            if not isinstance(parent, Tag):
                continue
            text = _clean(parent.get_text(" ", strip=True))
            if _DATE_RE.search(text) and len(text) < 1200:
                container = parent
                break

        text = _clean(container.get_text(" ", strip=True))
        published = _parse_dt(text)
        category = None
        for candidate in ["서면브리핑", "브리핑", "논평", "모두발언"]:
            if candidate in text and candidate not in title:
                category = candidate
                break
        if board is Board.OPENING_REMARKS and category is None:
            category = "모두발언"

        items.append(
            PostSummary(
                board=board,
                board_label=board.label,
                post_id=pid,
                category=category,
                title=title,
                published_at=published,
                url=urljoin(base_url + "/", href),
            )
        )
        seen.add(pid)
    return items


def parse_detail(html: str, board: Board, post_id: int, url: str) -> PostDetail:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text("\n", strip=True)

    title = None
    for selector in ["h3", "h2", ".title", ".subject", ".view_tit"]:
        node = soup.select_one(selector)
        if node:
            candidate = _clean(node.get_text(" ", strip=True))
            if candidate and candidate not in {"논평브리핑", "모두발언", "논평·브리핑"}:
                title = candidate
                break
    if not title:
        title = f"post-{post_id}"

    published = _parse_dt(page_text)
    author_match = _AUTHOR_RE.search(page_text)
    views_match = _VIEWS_RE.search(page_text)

    content_node = None
    for selector in [
        ".view_content",
        ".view_cont",
        ".board_view_content",
        ".board_view_con",
        ".content",
        "article",
    ]:
        node = soup.select_one(selector)
        if node and len(_clean(node.get_text(" ", strip=True))) > 20:
            content_node = node
            break

    if content_node:
        content = "\n".join(
            line.strip()
            for line in content_node.get_text("\n", strip=True).splitlines()
            if line.strip()
        )
    else:
        paragraphs = [
            _clean(node.get_text(" ", strip=True))
            for node in soup.find_all(["p", "div"])
            if 30 <= len(_clean(node.get_text(" ", strip=True))) <= 5000
        ]
        content = max(paragraphs, key=len, default="")

    attachments = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if any(token in href.lower() for token in ["download", "file", "attach"]):
            full = urljoin(url, href)
            if full not in attachments:
                attachments.append(full)

    category = "모두발언" if board is Board.OPENING_REMARKS else None
    return PostDetail(
        board=board,
        board_label=board.label,
        post_id=post_id,
        category=category,
        title=title,
        published_at=published,
        url=url,
        author=_clean(author_match.group(1)) if author_match else None,
        views=int(views_match.group(1).replace(",", "")) if views_match else None,
        content=content,
        attachments=attachments,
    )
