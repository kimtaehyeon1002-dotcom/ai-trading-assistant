"""TOP N 뉴스 선정 — 속보/매크로/반도체·AI 가중 후 최신순."""
from __future__ import annotations

from models.news import NewsArticle
from utils.dates import now_kst


def top(news: list[NewsArticle], n: int = 7) -> list[NewsArticle]:
    def weight(a: NewsArticle) -> int:
        w = 0
        if "breaking" in a.categories:
            w += 3
        if "macro" in a.categories:
            w += 1
        if "semiconductor" in a.categories or "ai" in a.categories:
            w += 1
        return w

    ranked = sorted(news, key=lambda a: (weight(a), a.published or now_kst()), reverse=True)
    return ranked[:n]
