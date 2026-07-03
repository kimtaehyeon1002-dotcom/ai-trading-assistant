"""매매일지 대시보드 생성 → docs/trades/index.html (지표 + 필터 + 이력)."""
from __future__ import annotations

from pathlib import Path

from calculators.trade_stats import compute_stats
from config.settings import DOCS_DIR
from generators.base import render
from models.trade import CATEGORY_LABELS
from repositories import trade_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.logging import get_logger

log = get_logger("gen.trades")


def generate() -> Path:
    trades = runlog.run_step("Trade Manager", trade_repository.load_trades, fallback=[]) or []
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
