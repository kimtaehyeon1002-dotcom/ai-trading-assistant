"""오늘 주목 테마 — 뉴스 키워드 빈도로 자동 산출(수기 지정·조작 금지). 키워드는 config/keywords."""
from __future__ import annotations

from calculators import keyword_match
from config.keywords import THEME_KEYWORDS
from models.news import NewsArticle


def extract_themes(articles: list[NewsArticle], top_n: int = 3) -> list[dict]:
    """[{name, count, sample}] — 근거(count>0) 있는 테마만, 빈도 내림차순 Top N."""
    counts: dict[str, int] = {}
    samples: dict[str, str] = {}
    for a in articles:
        text = keyword_match.text_of(a.title, a.summary)
        for theme, keywords in THEME_KEYWORDS.items():
            if keyword_match.any_match(keywords, text):
                counts[theme] = counts.get(theme, 0) + 1
                samples.setdefault(theme, a.title)
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:top_n]
    return [{"name": t, "count": c, "sample": samples[t]} for t, c in ranked]
