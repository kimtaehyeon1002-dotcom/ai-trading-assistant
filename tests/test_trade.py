from models.trade import DAY, LONG, SWING, Trade, classify_category


def test_classify_thresholds():
    assert classify_category(0) == DAY
    assert classify_category(1) == SWING
    assert classify_category(20) == SWING
    assert classify_category(21) == LONG


def test_trade_win_props():
    t = Trade(date="2026-06-01", ticker="005930", buy_price=100, sell_price=110, quantity=10, holding_days=0)
    assert t.category == DAY
    assert t.pnl == 100.0
    assert t.profit_pct == 10.0
    assert t.is_win is True


def test_trade_loss_props():
    t = Trade(date="2026-06-02", ticker="AAPL", buy_price=100, sell_price=90, quantity=5, holding_days=5)
    assert t.category == SWING
    assert t.pnl == -50.0
    assert t.profit_pct == -10.0
    assert t.is_win is False


def test_roundtrip_dict():
    t = Trade(date="2026-06-03", ticker="NVDA", buy_price=120, sell_price=142, quantity=20, holding_days=35)
    d = t.to_dict()
    assert d["category"] == LONG and d["pnl"] == 440.0
    t2 = Trade.from_dict(d)
    assert t2.pnl == t.pnl and t2.category == LONG
