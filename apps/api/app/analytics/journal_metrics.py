"""매매 메트릭 — 코드 계산(LLM 비의존, 정확·저비용). 설계서 §1.3-C, §2.4.

Notion 매매일지(완결 거래 1행: 날짜/종목/포지션/수익금/승·무·패)가 지원하는 지표만 계산하고,
데이터에 없는 지표(평균 보유기간·회전율·체결 시간대)는 unavailable로 정직하게 표기한다.
stdlib만 의존 → 네트워크/DB 없이 단위 테스트 가능.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

_WD = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass
class TradeInput:
    traded_on: date | None = None
    symbol: str | None = None
    position: str | None = None  # long | short
    pnl: float | None = None
    outcome: str = "unknown"  # win | loss | draw | unknown


def derive_outcome(
    *, win: bool = False, draw: bool = False, loss: bool = False, pnl: float | None = None
) -> str:
    """승/무/패 체크박스 우선, 없으면 수익금 부호로 결정."""
    if win:
        return "win"
    if loss:
        return "loss"
    if draw:
        return "draw"
    if pnl is None:
        return "unknown"
    if pnl > 0:
        return "win"
    if pnl < 0:
        return "loss"
    return "draw"


def _bucket_update(d: dict, key: str, pnl: float | None, outcome: str) -> None:
    b = d.setdefault(key, {"n": 0, "net_pnl": 0.0, "_w": 0, "_l": 0})
    b["n"] += 1
    if pnl is not None:
        b["net_pnl"] += pnl
    if outcome == "win":
        b["_w"] += 1
    elif outcome == "loss":
        b["_l"] += 1


def _finalize(d: dict) -> dict:
    out = {}
    for k, b in d.items():
        decided = b["_w"] + b["_l"]
        wr = (b["_w"] / decided) if decided else None
        out[k] = {
            "n": b["n"],
            "net_pnl": round(b["net_pnl"], 4),
            "win_rate": (round(wr, 4) if wr is not None else None),
        }
    return out


def compute_metrics(trades: list[TradeInput]) -> dict:
    n = len(trades)
    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    draws = [t for t in trades if t.outcome == "draw"]
    pnls = [t.pnl for t in trades if t.pnl is not None]
    win_pnls = [t.pnl for t in wins if t.pnl is not None]
    loss_pnls = [t.pnl for t in losses if t.pnl is not None]

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = sum(p for p in pnls if p < 0)  # 음수
    net = sum(pnls)
    decided = len(wins) + len(losses)
    win_rate = (len(wins) / decided) if decided else None
    avg_win = (sum(win_pnls) / len(win_pnls)) if win_pnls else None
    avg_loss = (sum(loss_pnls) / len(loss_pnls)) if loss_pnls else None  # 음수
    avg_trade = (net / len(pnls)) if pnls else None
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None
    payoff = (avg_win / abs(avg_loss)) if (avg_win is not None and avg_loss) else None
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    # 연속 승/패 + 누적손익 곡선 MDD (날짜→원래 순서로 정렬)
    ordered = sorted(range(n), key=lambda i: (trades[i].traded_on or date.min, i))
    max_w = cur_w = max_l = cur_l = 0
    equity = peak = mdd = 0.0
    for i in ordered:
        t = trades[i]
        if t.outcome == "win":
            cur_w, cur_l = cur_w + 1, 0
        elif t.outcome == "loss":
            cur_l, cur_w = cur_l + 1, 0
        else:
            cur_w = cur_l = 0
        max_w, max_l = max(max_w, cur_w), max(max_l, cur_l)
        if t.pnl is not None:
            equity += t.pnl
            peak = max(peak, equity)
            mdd = max(mdd, peak - equity)

    by_symbol: dict = {}
    by_position: dict = {}
    by_weekday: dict = {}
    for t in trades:
        _bucket_update(by_symbol, t.symbol or "UNKNOWN", t.pnl, t.outcome)
        _bucket_update(by_position, (t.position or "unknown"), t.pnl, t.outcome)
        wd = _WD[t.traded_on.weekday()] if t.traded_on else "?"
        _bucket_update(by_weekday, wd, t.pnl, t.outcome)

    def _r(x):
        return round(x, 4) if x is not None else None

    return {
        "n_trades": n,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_draws": len(draws),
        "win_rate": _r(win_rate),
        "net_pnl": round(net, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "avg_win": _r(avg_win),
        "avg_loss": _r(avg_loss),
        "avg_trade": _r(avg_trade),
        "profit_factor": _r(profit_factor),
        "payoff_ratio": _r(payoff),
        "expectancy": _r(expectancy),
        "max_win_streak": max_w,
        "max_loss_streak": max_l,
        "max_drawdown": round(mdd, 4),
        "by_symbol": _finalize(by_symbol),
        "by_position": _finalize(by_position),
        "by_weekday": _finalize(by_weekday),
        "unavailable": ["avg_holding_period", "turnover", "intraday_time_of_day"],
    }
