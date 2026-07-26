"""TOP N 뉴스 선정 — 속보/매크로/반도체·AI 가중 후 최신순."""
from __future__ import annotations

from datetime import datetime, timezone

from models.news import NewsArticle

# published 결측 시 "지금 막 발행"이 아니라 "가장 오래된" 취급 — calculators/news_levels.py,
# repositories/news_repository.py와 동일 관례(결측 기사가 최신 취급되어 동점 가중치 구간에서
# 실제로 시각이 찍힌 최신 기사를 밀어내는 걸 방지).
_OLD = datetime(1970, 1, 1, tzinfo=timezone.utc)


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

    ranked = sorted(news, key=lambda a: (weight(a), a.published or _OLD), reverse=True)
    return ranked[:n]
