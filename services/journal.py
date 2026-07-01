"""매매일지 저장소 — data/trades/trades.json 로드/저장/추가(멱등 dedup).

Kiwoom 체결이 여기로 적재되고, generators/trades가 이 데이터로 대시보드를 만든다.
"""
from __future__ import annotations

from config.settings import TRADES_DIR
from core.jsonio import load_json, save_json
from core.logging import get_logger
from models.trade import Trade

log = get_logger("journal")
_STORE = TRADES_DIR / "trades.json"


def load_trades() -> list[Trade]:
    return [Trade.from_dict(d) for d in (load_json(_STORE, default=[]) or [])]


def save_trades(trades: list[Trade]) -> None:
    trades = sorted(trades, key=lambda t: t.date, reverse=True)
    save_json(_STORE, [t.to_dict() for t in trades])


def _key(t: Trade) -> tuple:
    return (t.date, t.ticker, round(t.sell_price, 4), round(t.quantity, 4))


def add_trades(new: list[Trade]) -> list[Trade]:
    """신규 체결을 dedup 후 병합 저장. 반환=전체 목록."""
    existing = load_trades()
    seen = {_key(t) for t in existing}
    added = 0
    for t in new:
        if _key(t) not in seen:
            existing.append(t)
            seen.add(_key(t))
            added += 1
    save_trades(existing)
    log.info("매매일지 추가 %d건 (총 %d건)", added, len(existing))
    return existing
