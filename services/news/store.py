"""뉴스 캐시 — 링크 해시로 dedup, 신선도 순 정렬 저장(30분 주기 누적)."""
from __future__ import annotations

from datetime import datetime, timezone

from config.settings import CACHE_DIR
from core.jsonio import load_json, save_json
from models.news import NewsArticle

_CACHE = CACHE_DIR / "news.json"
_OLD = datetime(1970, 1, 1, tzinfo=timezone.utc)


def load_cached() -> list[NewsArticle]:
    return [NewsArticle.from_dict(d) for d in (load_json(_CACHE, default=[]) or [])]


def merge_and_save(new: list[NewsArticle], keep: int = 400) -> list[NewsArticle]:
    by_id = {a.id: a for a in load_cached()}
    for a in new:
        by_id[a.id] = a  # 최신 메타로 갱신
    merged = sorted(by_id.values(), key=lambda x: x.published or _OLD, reverse=True)[:keep]
    save_json(_CACHE, [a.to_dict() for a in merged])
    return merged
