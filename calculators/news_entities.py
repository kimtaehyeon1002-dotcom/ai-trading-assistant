"""관련 종목 태깅 — config/entities.py 큐레이션 세트를 제목·요약에서 매칭(design/20 Phase 5)."""
from __future__ import annotations

from config.entities import ENTITIES
from models.news import NewsArticle


def extract_impact_tags(article: NewsArticle) -> list[dict]:
    """제목+요약에서 매칭된 종목을 [{ticker, name, market}, ...]로 반환(티커 중복 제거)."""
    text = f"{article.title} {article.summary}".lower()
    seen: set[str] = set()
    tags: list[dict] = []
    for name, (ticker, display, market) in ENTITIES.items():
        if name in text and ticker not in seen:
            seen.add(ticker)
            tags.append({"ticker": ticker, "name": display, "market": market})
    return tags


def assign(articles: list[NewsArticle]) -> list[NewsArticle]:
    for a in articles:
        a.impact_tags = extract_impact_tags(a)
    return articles
