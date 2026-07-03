"""뉴스 카테고리 분류 — 지역 + 키워드(config/keywords) + 속보(신선도)."""
from __future__ import annotations

from config.keywords import CATEGORY_KEYWORDS
from config.settings import BREAKING_WINDOW_MIN
from models.news import NewsArticle
from utils.dates import within_minutes


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


def assign(articles: list[NewsArticle]) -> list[NewsArticle]:
    """카테고리 일괄 부여(멱등)."""
    for a in articles:
        a.categories = categorize(a)
    return articles
