"""뉴스 카테고리 분류 — 지역 + 제목/요약 키워드 + 속보(신선도)."""
from __future__ import annotations

from config.feeds import CATEGORY_KEYWORDS
from config.settings import BREAKING_WINDOW_MIN
from core.dates import within_minutes
from models.news import NewsArticle


def categorize(article: NewsArticle) -> list[str]:
    cats: list[str] = []
    if article.region == "KR":
        cats.append("kr_market")
    elif article.region == "US":
        cats.append("us_market")

    text = f"{article.title} {article.summary}".lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            cats.append(cat)

    if article.published and within_minutes(article.published, BREAKING_WINDOW_MIN):
        cats.append("breaking")
    return cats
