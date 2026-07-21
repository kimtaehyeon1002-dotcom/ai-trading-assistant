"""매매일지 v2 생성 → docs/trades/index.html(design/20 Phase 8 "공개 v2 치환", URL 유지·게이트 없음).

design/09 Portfolio에는 매매일지 화면이 정의되어 있지 않고 Portfolio는 비번 게이트 뒤이므로,
"Portfolio 흡수" 안은 채택하지 않는다(design/20 §254) — 매매일지는 계속 공개 서비스로 유지되며
암호화도 필요 없다(개인 잔고가 아니라 이미 청산된 매매 기록·통계).
"""
from __future__ import annotations

from pathlib import Path

from calculators.trade_stats import compute_stats
from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from models.trade import CATEGORY_LABELS
from repositories import trade_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.logging import get_logger

log = get_logger("gen.trades_v2")


def generate() -> Path:
    trades = runlog.run_step("Trade Manager", trade_repository.load_trades, fallback=[]) or []
    stats = compute_stats(trades)
    out = render(
        "pages/trades_v2.html",
        {
            "root": "..",
            "nav": nav.context(active="trades"),
            "generated_at": fmt_kst(now_kst()) + " KST",
            "trades": trades,
            "stats": stats,
            "labels": CATEGORY_LABELS,
        },
        DOCS_DIR / "trades" / "index.html",
    )
    log.info("매매일지 v2 생성: %s (%d건)", out, len(trades))
    return out
