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


# News 4탭 taxonomy(design/03 §1-3) — 배타 매핑 우선순위 breaking > macro > kr/us(design/20 Phase 5
# 체크리스트 "6카테고리 → 4탭 배타 매핑"). 한 기사는 정확히 1개 탭에만 속한다(속보만 다른 시장
# 분류를 흡수해 통합 표시 — design/03 DoD "탭이 배타적이다, 속보만 통합").
TAB_LABELS = {"breaking": "속보", "macro": "거시경제", "kr_market": "한국시장", "us_market": "미국시장"}
_PRIORITY = ("breaking", "macro", "kr_market", "us_market")


def primary_category(article: NewsArticle) -> str | None:
    """4탭 중 이 기사가 속할 정확히 하나의 카테고리 키(없으면 None — 게재 기준 미달)."""
    for cat in _PRIORITY:
        if cat in article.categories:
            return cat
    return None


def primary_label(article: NewsArticle) -> str:
    cat = primary_category(article)
    return TAB_LABELS.get(cat, "기타")
