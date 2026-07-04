"""랜딩(대시보드) 생성 → docs/index.html (모듈 링크 + 최신 스냅샷)."""
from __future__ import annotations

from pathlib import Path

from calculators.trade_stats import compute_stats
from config.settings import DOCS_DIR
from generators.base import render
from generators.morning.generate import list_dates
from repositories import trade_repository
from utils.dates import fmt_kst, now_kst
from utils.logging import get_logger

log = get_logger("gen.dashboard")


def generate() -> Path:
    dates = list_dates()
    latest = dates[0] if dates else None
    stats = compute_stats(trade_repository.load_trades())
    ctx = {
        "active": "home",
        "root": ".",
        "latest_morning": latest,
        "stats": stats,
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    out = render("dashboard.html", ctx, DOCS_DIR / "index.html")
    log.info("대시보드 생성: %s", out)
    return out
