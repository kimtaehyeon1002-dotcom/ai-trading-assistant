"""RSS 뉴스 어댑터. 저작권 안전: 헤드라인 + 링크 + (자체)요약만, 본문 미저장.

dedup 키 = sha256(url). 향후 SimHash 근사중복은 RAG 인입(Phase 6)에서 보강.
"""
from __future__ import annotations

import asyncio
import hashlib

from app.data_providers.base import NewsProvider
from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import now_utc, to_utc
from app.schemas.market import NewsItem, ProviderMeta

# 헤드라인+링크만 사용하는 공개 RSS (본문 전문 저장/재배포 금지)
_FEEDS: dict[str, list[str]] = {
    "ko": ["https://www.hankyung.com/feed/finance"],
    "en": ["https://feeds.a.dj.com/rss/RSSMarketsMain.xml"],
}


def _dedup_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


class RssNewsProvider(NewsProvider):
    name = "rss"
    tier = "free"
    markets = ("KR", "US")
    is_realtime = True  # 발행 즉시(분 단위)
    priority = 50

    async def get_news(
        self, market: str | None, symbols: list[str] | None, lang: str | None, limit: int
    ) -> list[NewsItem]:
        return await asyncio.to_thread(self._news_sync, lang, limit)

    def _news_sync(self, lang: str | None, limit: int) -> list[NewsItem]:
        try:
            import feedparser

            langs = [lang] if lang in _FEEDS else list(_FEEDS.keys())
            items: list[NewsItem] = []
            for lg in langs:
                for url in _FEEDS.get(lg, []):
                    parsed = feedparser.parse(url)
                    for e in parsed.entries[:limit]:
                        link = getattr(e, "link", "")
                        if not link:
                            continue
                        published = now_utc()
                        if getattr(e, "published_parsed", None):
                            import calendar
                            from datetime import datetime, timezone

                            published = to_utc(
                                datetime.fromtimestamp(
                                    calendar.timegm(e.published_parsed), tz=timezone.utc
                                )
                            )
                        items.append(
                            NewsItem(
                                id=_dedup_id(link),
                                title=getattr(e, "title", "")[:500],
                                summary=(getattr(e, "summary", "") or "")[:280] or None,
                                url=link,
                                source_name=parsed.feed.get("title", lg),
                                language=lg,
                                published_at=published,
                                symbols=[],
                                meta=ProviderMeta(
                                    source=self.name, is_realtime=True, as_of=now_utc()
                                ),
                            )
                        )
            items.sort(key=lambda x: x.published_at, reverse=True)
            return items[:limit]
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(f"rss error: {exc}") from exc
