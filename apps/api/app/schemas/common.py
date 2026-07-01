"""공통 응답 스키마: 에러(RFC9457 유사) + 커서 페이지네이션 봉투."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str | None = None
    request_id: str | None = None


class PageMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False
    limit: int = 20


class Page(BaseModel, Generic[T]):
    data: list[T]
    page: PageMeta
