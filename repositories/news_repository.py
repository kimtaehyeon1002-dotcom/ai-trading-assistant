"""검증된 뉴스 raw → NewsArticle 정규화 + 기사 저장소(cache/news_articles.json) 병합.

주의: 기사 저장소 파일은 news_articles.json — 리포트 산출물(cache/news.json)과 분리
(과거 동일 경로 사용으로 스키마 충돌 크래시 위험이 있었음).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from config.settings import CACHE_DIR
from models.news import NewsArticle
from utils.jsonio import load_json, save_json

_STORE = CACHE_DIR / "news_articles.json"
_OLD = datetime(1970, 1, 1, tzinfo=timezone.utc)
_TAG = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return _TAG.sub("", html or "").replace("&nbsp;", " ").strip()


def to_articles(rows: list[dict]) -> list[NewsArticle]:
    """raw → 정규화 모델(HTML 제거·길이 제한). 요약은 원문 추출식 그대로(재작성 금지)."""
    return [
        NewsArticle(
            title=_clean(r["title"])[:300],
            link=r["link"],
            source=r.get("source", ""),
            published=r.get("published"),
            summary=_clean(r.get("summary_html", ""))[:280],
            region=r.get("region", ""),
            lang=r.get("lang", "ko"),
        )
        for r in rows
    ]


def load_store() -> list[NewsArticle]:
    raw = load_json(_STORE, default=[])
    if not isinstance(raw, list):  # 스키마 오염 방어
        return []
    return [NewsArticle.from_dict(d) for d in raw if isinstance(d, dict)]


def merge_and_save(new: list[NewsArticle], keep: int = 400) -> list[NewsArticle]:
    """링크 해시 기준 병합(중복 제거) 후 최신순 keep건 유지.

    first_seen_at은 저장소에 최초로 들어온 시각으로 고정한다 — 이미 있던 기사를 재병합해도
    덮어쓰지 않는다(design/20 Phase 5, "신규 도트"는 최초 발견 시각을 기준으로 판정해야 하므로).
    """
    existing = {a.id: a for a in load_store()}
    now_iso = datetime.now(timezone.utc).isoformat()
    for a in new:
        prev = existing.get(a.id)
        a.first_seen_at = prev.first_seen_at if prev and prev.first_seen_at else now_iso
        existing[a.id] = a
    merged = sorted(existing.values(), key=lambda x: x.published or _OLD, reverse=True)[:keep]
    save_json(_STORE, [a.to_dict() for a in merged])
    return merged
