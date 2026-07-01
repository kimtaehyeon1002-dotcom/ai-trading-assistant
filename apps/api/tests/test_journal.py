"""Phase 4 — 매매 메트릭(순수) + 코치 스텁 가드레일 + Notion 매핑. 메트릭/코치는 오프라인 실행 가능.

notion_provider는 config(pydantic-settings) 의존 → Docker/uv 환경에서 실행.
"""
from __future__ import annotations

from datetime import date

from app.agents.prompts import coach as C
from app.analytics.journal_metrics import TradeInput, compute_metrics, derive_outcome
from app.compliance.guard import guard_output


def _trades():
    return [
        TradeInput(date(2026, 6, 1), "BTC", "long", 120.0, "win"),
        TradeInput(date(2026, 6, 2), "BTC", "long", -60.0, "loss"),
        TradeInput(date(2026, 6, 3), "ETH", "short", 200.0, "win"),
        TradeInput(date(2026, 6, 4), "ETH", "short", -40.0, "loss"),
        TradeInput(date(2026, 6, 5), "SOL", "long", -25.0, "loss"),
        TradeInput(date(2026, 6, 8), "BTC", "long", 0.0, "draw"),
    ]


def test_derive_outcome():
    assert derive_outcome(win=True) == "win"
    assert derive_outcome(loss=True) == "loss"
    assert derive_outcome(draw=True) == "draw"
    assert derive_outcome(pnl=10) == "win" and derive_outcome(pnl=-5) == "loss"
    assert derive_outcome(pnl=0) == "draw" and derive_outcome() == "unknown"


def test_metrics_basic():
    m = compute_metrics(_trades())
    assert m["n_trades"] == 6 and m["n_wins"] == 2 and m["n_losses"] == 3 and m["n_draws"] == 1
    assert m["win_rate"] == round(2 / 5, 4)
    assert m["net_pnl"] == 195.0  # 120-60+200-40-25+0
    assert m["gross_profit"] == 320.0 and m["gross_loss"] == -125.0
    assert m["profit_factor"] == round(320 / 125, 4)
    assert m["max_loss_streak"] == 2 and m["max_drawdown"] > 0
    assert set(m["by_position"]) == {"long", "short"}
    assert "avg_holding_period" in m["unavailable"]


def test_metrics_empty_safe():
    m = compute_metrics([])
    assert m["n_trades"] == 0 and m["win_rate"] is None and m["profit_factor"] is None
    assert m["net_pnl"] == 0.0


def test_coach_stub_passes_guardrail():
    m = compute_metrics(_trades())
    md = C.stub_coach_markdown(m, is_trade_decision=True)
    res = guard_output(md)
    assert res.blocked is False, res.categories  # 매수/매도·목표가 트리거 없어야 함
    for h in (C.H_PERF, C.H_PAT, C.H_CHK, C.H_RISK):
        assert h in md


def test_parse_coach_blocks():
    m = compute_metrics(_trades())
    md = C.stub_coach_markdown(m)
    blocks = C.parse_coach_blocks(md)
    assert blocks["performance"] and blocks["patterns"]
    assert blocks["checklist"] and blocks["risks"]
