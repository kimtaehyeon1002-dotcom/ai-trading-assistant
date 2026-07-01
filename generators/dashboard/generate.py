"""랜딩(대시보드) 생성 → docs/index.html (모듈 링크 + 최신 스냅샷)."""
from __future__ import annotations

from pathlib import Path

from config.settings import DOCS_DIR
from core.dates import fmt_kst, now_kst
from core.logging import get_logger
from generators.base import render
from services import journal
from services.report.trades import compute_stats

log = get_logger("gen.dashboard")


def generate() -> Path:
    mbase = DOCS_DIR / "morning"
    latest = None
    if mbase.exists():
        dates = sorted(
            [p.name for p in mbase.iterdir() if p.is_dir() and p.name[:1].isdigit()], reverse=True
        )
        latest = dates[0] if dates else None
    stats = compute_stats(journal.load_trades())
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
