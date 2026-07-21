"""중요도 등급(L1~L3) 판정 — 규칙 기반 점수, 일별 L3 상한 강제(design/20 Phase 5 DoD 3, design/03 §1-4).

판정은 해석(AI)이 아니라 이미 존재하는 사실 신호(카테고리·관련종목 매칭)의 규칙 조합이다.
- macro(금리·물가·환율 등): 지수·환율·금리 직접 영향 신호 → 가중치 2
- 관련 종목 매칭: 시총 상위 종목 직접 영향 신호 → 가중치 1
- semiconductor/ai: 주요 섹터 직접 영향 신호 → 가중치 1
점수 3점 이상만 L3 후보이며, 하루(KST 날짜) 상한(기본 5건)을 넘으면 상위 우선순위만 L3를 유지하고
초과분은 L2로 강등한다(design/03 §1-4 "하루 기대 건수" 상한 준수).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from models.news import NewsArticle
from utils.dates import to_kst

L3_DAILY_CAP = 5
_OLD = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _score(article: NewsArticle) -> int:
    s = 0
    if "macro" in article.categories:
        s += 2
    if article.impact_tags:
        s += 1
    if "semiconductor" in article.categories or "ai" in article.categories:
        s += 1
    return s


def assign_levels(articles: list[NewsArticle]) -> list[NewsArticle]:
    """articles를 KST 날짜별로 묶어 각 날짜 안에서만 L3 상한을 적용한다(하루 기대 건수 개념)."""
    by_day: dict[str, list[NewsArticle]] = defaultdict(list)
    for a in articles:
        day = to_kst(a.published).strftime("%Y-%m-%d") if a.published else "unknown"
        by_day[day].append(a)

    for day_articles in by_day.values():
        ranked = sorted(day_articles, key=lambda a: (_score(a), a.published or _OLD), reverse=True)
        l3_used = 0
        for a in ranked:
            s = _score(a)
            if s >= 3 and l3_used < L3_DAILY_CAP:
                a.level = "L3"
                l3_used += 1
            elif s >= 1:
                a.level = "L2"
            else:
                a.level = "L1"
    return articles
