"""Stock 페이지 생성 → docs/stock/index.html (랭킹·유니버스·Hub 발행은 파이프라인이 담당).

design/04, design/20 Phase 7. design/21 §225·§8: 미국은 전종목 무료 스냅샷이 없어 S&P500
유니버스 내 TOP30으로 축소하고 모집단 캡션으로 고지한다.

design/25 Phase B: 수집·검증·발행은 pipelines.get_stock()으로 이동했다 — 이 모듈은 렌더만 한다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from repositories import stock_repository
from utils.dates import fmt_kst, now_kst


def _table_freshness(table: dict | None) -> dict | None:
    if not table:
        return None
    fresh = stock_repository.freshness_attrs()
    return {
        "as_of_iso": table["as_of_iso"],
        "fresh_max_min": fresh["fresh_max_min"],
        "stale_min_min": fresh["stale_min_min"],
        "session_key": table["session_key"],
    }


def generate() -> Path:
    body = pipelines.get_stock()["body"]
    out = DOCS_DIR / "stock" / "index.html"
    return render(
        "pages/stock.html",
        {
            "root": "..",
            "nav": nav.context(active="stock"),
            "generated_at": fmt_kst(now_kst()) + " KST",
            "kr": body["kr"],
            "us": body["us"],
            "freshness_kr": _table_freshness(body["kr"]),
            "freshness_us": _table_freshness(body["us"]),
        },
        out,
    )
