"""매매 통계 — 승률/평균손익/카테고리·월별 집계(순수 계산, LLM 비의존)."""
from __future__ import annotations

from collections import defaultdict

from models.trade import Trade, TradeStats


def compute_stats(trades: list[Trade]) -> TradeStats:
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    decided = len(wins) + len(losses)
    win_pnls = [t.pnl for t in wins]
    loss_pnls = [t.pnl for t in losses]

    by_cat: dict = defaultdict(lambda: {"n": 0, "pnl": 0.0, "w": 0, "l": 0})
    monthly: dict = defaultdict(float)
    for t in trades:
        c = by_cat[t.category]
        c["n"] += 1
        c["pnl"] += t.pnl
        if t.pnl > 0:
            c["w"] += 1
        elif t.pnl < 0:
            c["l"] += 1
        monthly[(t.date or "")[:7]] += t.pnl

    by_category = {
        k: {
            "n": v["n"],
            "pnl": round(v["pnl"], 2),
            "win_rate": (round(v["w"] / (v["w"] + v["l"]) * 100, 1) if (v["w"] + v["l"]) else None),
        }
        for k, v in by_cat.items()
    }

    return TradeStats(
        n_trades=n,
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=round(len(wins) / decided * 100, 1) if decided else None,
        total_pnl=round(sum(t.pnl for t in trades), 2),
        avg_profit=round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else None,
        avg_loss=round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else None,
        by_category=by_category,
        monthly={k: round(monthly[k], 2) for k in sorted(monthly) if k},
    )
