"""Stock 페이지 생성 — KR/US 거래대금 TOP30 + 종목 유니버스 병합(design/04, design/20 Phase 7).

design/21 §225·§8: 미국은 전종목 무료 스냅샷이 없어 S&P500 유니버스 내 TOP30으로 축소하고
모집단 캡션으로 고지한다. 유니버스(=TOP30×2 ∪ 테마 ∪ Notion watchlist)는 이 생성기가 확정해
docs/data/stock/universe.json으로 발행한다 — Stock Hub·검색 인덱스가 이 파일로 "유니버스 내
종목인가"를 판정한다(design/21 §365).
"""
from __future__ import annotations

from pathlib import Path

from collectors import krx_ranking_collector, us_ranking_collector
from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from repositories import notion_repository, stock_repository
from repositories.news_repository import load_store
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.jsonio import save_json
from validators import ranking_validator


def _build_kr() -> list[dict] | None:
    raw = runlog.run_step("Stock KR Ranking", krx_ranking_collector.collect, fallback=None)
    return ranking_validator.validate(raw)


def _build_us() -> list[dict] | None:
    raw = runlog.run_step("Stock US Ranking", us_ranking_collector.collect, fallback=None)
    return ranking_validator.validate(raw)


def _watchlist_rows() -> list[dict]:
    cached = notion_repository.load_normalized()
    if not cached:
        return []
    return cached.get("databases", {}).get("watchlist", [])


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
    kr_rows = _build_kr()
    us_rows = _build_us()

    body = stock_repository.build(kr_rows, us_rows)
    stock_repository.persist(body)

    universe = stock_repository.build_universe(kr_rows, us_rows, _watchlist_rows())
    save_json(DOCS_DIR / "data" / "stock" / "universe.json",
              [{"code": c, "name": n, "market": m} for c, n, m in universe])

    # S&P500 후보 밖 US 테마·watchlist 종목(예: TSM, NVO)은 배치 랭킹에 없으므로 보조 조회한다.
    us_covered = {r["code"] for r in (us_rows or [])}
    kr_codes = {r["code"] for r in (kr_rows or [])}
    missing_us = [c for c, _n, m in universe if m not in stock_repository.KR_MARKETS
                  and c not in us_covered and c not in kr_codes]
    supplementary = runlog.run_step(
        "Stock Hub 보조시세", lambda: us_ranking_collector.collect_quotes(missing_us), fallback={},
    )

    articles = load_store()
    hub_entries = stock_repository.build_hub_entries(kr_rows, us_rows, universe, supplementary, articles)
    stock_repository.persist_hub(hub_entries)

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
