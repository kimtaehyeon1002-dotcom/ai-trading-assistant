"""RSS 수집 — feedparser로 SOURCES 순회. 개별 피드 실패는 건너뜀(부분 성공)."""
from __future__ import annotations

import calendar as _cal
import re
from datetime import datetime, timezone

from config.feeds import SOURCES
from config.settings import NEWS_FETCH_LIMIT
from core.logging import get_logger
from models.news import NewsArticle
from services.news.categorize import categorize

log = get_logger("news.collector")

_TAG = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return _TAG.sub("", html or "").replace("&nbsp;", " ").strip()


def collect() -> list[NewsArticle]:
    try:
        import feedparser
    except Exception as exc:  # noqa: BLE001
        log.warning("feedparser 미설치: %s", exc)
        return []

    articles: list[NewsArticle] = []
    for src in SOURCES:
        try:
            parsed = feedparser.parse(src["url"])
            for e in parsed.entries[:NEWS_FETCH_LIMIT]:
                link = getattr(e, "link", "")
                if not link:
                    continue
                published = None
                if getattr(e, "published_parsed", None):
                    published = datetime.fromtimestamp(
                        _cal.timegm(e.published_parsed), tz=timezone.utc
                    )
                art = NewsArticle(
                    title=_clean(getattr(e, "title", ""))[:300],
                    link=link,
                    source=src["source"],
                    published=published,
                    summary=_clean(getattr(e, "summary", ""))[:280],
                    region=src["region"],
                    lang=src["lang"],
                )
                art.categories = categorize(art)
                articles.append(art)
        except Exception as exc:  # noqa: BLE001
            log.warning("피드 실패 %s: %s", src["url"], exc)
    log.info("뉴스 수집 %d건 (%d소스)", len(articles), len(SOURCES))
    return articles
