"""repositories/trade_repository.py — dedup 키가 buy_price를 구분하는지 검증."""
from __future__ import annotations

from models.trade import Trade
from repositories import trade_repository


def _trade(buy_price, sell_price=110, quantity=10):
    return Trade(date="2026-07-01", ticker="005930", buy_price=buy_price, sell_price=sell_price,
                 quantity=quantity, holding_days=0, broker="kiwoom")


def test_add_trades_dedups_true_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(trade_repository, "_STORE", tmp_path / "trades.json")
    t = _trade(buy_price=100)
    trade_repository.add_trades([t])
    result = trade_repository.add_trades([_trade(buy_price=100)])  # 완전히 동일한 체결 재수신
    assert len(result) == 1


def test_add_trades_keeps_distinct_buy_price_same_day_ticker_sell_qty(tmp_path, monkeypatch):
    # 같은 날/종목/체결가/수량이라도 매입단가가 다르면(분할 매수 후 별개 청산) 별개 체결이다.
    monkeypatch.setattr(trade_repository, "_STORE", tmp_path / "trades.json")
    trade_repository.add_trades([_trade(buy_price=100)])
    result = trade_repository.add_trades([_trade(buy_price=105)])
    assert len(result) == 2
