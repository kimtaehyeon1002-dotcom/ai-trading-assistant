"""repositories/trade_repository.py — dedup 키·kiwoom 변환(매매일지 손실 방지 회귀)."""
from __future__ import annotations

from models.trade import Trade
from repositories import trade_repository


def _trade(**overrides):
    base = dict(date="2026-07-20", ticker="005930", name="삼성전자", buy_price=70000.0,
                sell_price=72000.0, quantity=10.0, holding_days=1, account_type="위탁", broker="kiwoom")
    base.update(overrides)
    return Trade(**base)


def test_add_trades_keeps_distinct_lots_with_same_date_ticker_price_qty(tmp_path, monkeypatch):
    """같은 날/종목/매도가/수량이라도 매입단가(원가)가 다르면 서로 다른 체결 — 병합 시 사라지면 안 된다."""
    monkeypatch.setattr(trade_repository, "_STORE", tmp_path / "trades.json")

    lot_a = _trade(buy_price=70000.0)
    lot_b = _trade(buy_price=65000.0)  # 별도 매수 로트, 나머지 필드 동일

    trade_repository.add_trades([lot_a])
    result = trade_repository.add_trades([lot_b])

    assert len(result) == 2, "매입단가가 다른 별개 체결이 dedup으로 소실됨"


def test_add_trades_dedups_true_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(trade_repository, "_STORE", tmp_path / "trades.json")
    t = _trade()
    trade_repository.add_trades([t])
    result = trade_repository.add_trades([_trade()])
    assert len(result) == 1
