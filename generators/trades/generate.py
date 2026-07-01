"""매매일지 대시보드 생성 → docs/trades/index.html (지표 + 필터 + 이력)."""
from __future__ import annotations

from pathlib import Path

from config.settings import DOCS_DIR
from core.dates import fmt_kst, now_kst
from core.logging import get_logger
from generators.base import render
from models.trade import CATEGORY_LABELS
from services import journal
from services.report.trades import compute_stats

log = get_logger("gen.trades")


def generate() -> Path:
    trades = journal.load_trades()
    stats = compute_stats(trades)
    ctx = {
        "active": "trades",
        "root": "..",
        "trades": trades,
        "stats": stats,
        "labels": CATEGORY_LABELS,
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    out = render("trades.html", ctx, DOCS_DIR / "trades" / "index.html")
    log.info("매매일지 생성: %s (%d건)", out, len(trades))
    return out
