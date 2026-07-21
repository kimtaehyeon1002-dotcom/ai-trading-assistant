"""글로벌 검색 인덱스(design/00 §7-2, design/20 Phase 7) — 종목/뉴스/페이지 3그룹 병합.

이미 발행·캐시된 산출물(종목 유니버스·뉴스 저장소)만 읽어 조립한다 — 이 리포지토리 자체는
어떤 데이터도 새로 수집하지 않는다. build.py 공통 마무리 단계에서 어떤 target을 빌드하든
매번 재생성한다(대시보드·AI Office와 동일한 "항상 최신 상태 유지" 원칙).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import nav
from config.settings import DOCS_DIR
from utils.jsonio import load_json, save_json

_MAX_NEWS = 50


def _pages() -> list[dict]:
    items = [*nav.MAIN_ITEMS, *nav.LOCKED_ITEMS, nav.SETTINGS_ITEM]
    return [{"key": i.key, "label": i.label, "href": i.href} for i in items]


def _stocks() -> list[dict]:
    data = load_json(DOCS_DIR / "data" / "stock" / "universe.json", default=[])
    if not isinstance(data, list):
        return []
    return [
        {"code": r["code"], "name": r["name"], "market": r["market"]}
        for r in data if isinstance(r, dict) and r.get("code")
    ]


def _news(articles: list) -> list[dict]:
    return [
        {"title": a.title, "link": a.link, "source": a.source,
         "published": a.published.isoformat() if a.published else None}
        for a in articles[:_MAX_NEWS]
    ]


def build(articles: list) -> dict:
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "stocks": _stocks(),
        "news": _news(articles),
        "pages": _pages(),
    }


def persist(body: dict) -> None:
    save_json(DOCS_DIR / "data" / "search-index.json", body)
