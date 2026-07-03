"""뉴스 RSS 수집 — feedparser로 SOURCES 순회, raw dict 반환(모델 변환은 repositories/).

개별 피드 실패는 건너뜀(부분 성공). 실행당 1회만 다운로드(메모이즈).
"""
from __future__ import annotations

import calendar as _cal
from datetime import datetime, timezone

from config.feeds import SOURCES
from config.settings import NEWS_FETCH_LIMIT
from utils.logging import get_logger

log = get_logger("collectors.news")

_memo: list[dict] | None = None


def collect() -> list[dict]:
    """raw 기사: {title, link, summary_html, published(dt|None), source, region, lang}."""
    global _memo
    if _memo is not None:
        return _memo

    try:
        import feedparser
    except Exception as exc:  # noqa: BLE001
        log.warning("feedparser 미설치: %s", exc)
        return []

    rows: list[dict] = []
    for src in SOURCES:
        try:
            parsed = feedparser.parse(src["url"])
            for e in parsed.entries[:NEWS_FETCH_LIMIT]:
                published = None
                if getattr(e, "published_parsed", None):
                    published = datetime.fromtimestamp(
                        _cal.timegm(e.published_parsed), tz=timezone.utc
                    )
                rows.append(
                    {
                        "title": getattr(e, "title", ""),
                        "link": getattr(e, "link", ""),
                        "summary_html": getattr(e, "summary", "") or "",
                        "published": published,
                        "source": src["source"],
                        "region": src["region"],
                        "lang": src["lang"],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("피드 실패 %s: %s", src["url"], exc)
    log.info("뉴스 수집 %d건 (%d소스)", len(rows), len(SOURCES))
    _memo = rows
    return rows
