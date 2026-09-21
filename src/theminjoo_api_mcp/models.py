from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, Field, HttpUrl


class Board(IntEnum):
    BRIEFINGS = 11
    OPENING_REMARKS = 230

    @property
    def label(self) -> str:
        return "논평·브리핑" if self is Board.BRIEFINGS else "모두발언"


class PostSummary(BaseModel):
    board: Board
    board_label: str
    post_id: int
    category: str | None = None
    title: str
    published_at: datetime | None = None
    url: HttpUrl


class PostDetail(PostSummary):
    author: str | None = None
    views: int | None = None
    content: str = ""
    attachments: list[HttpUrl] = Field(default_factory=list)


class PostList(BaseModel):
    items: list[PostSummary]
    board: Board
    offset: int
    limit: int
    next_offset: int | None = None
