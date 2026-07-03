from models.trade import Trade
from calculators.trade_stats import compute_stats


def _sample():
    return [
        Trade(date="2026-06-01", ticker="A", buy_price=100, sell_price=120, quantity=10, holding_days=0),
        Trade(date="2026-06-02", ticker="B", buy_price=100, sell_price=80, quantity=10, holding_days=5),
        Trade(date="2026-06-03", ticker="C", buy_price=100, sell_price=130, quantity=10, holding_days=35),
    ]


def test_stats_basic():
    s = compute_stats(_sample())
    assert s.n_trades == 3 and s.n_wins == 2 and s.n_losses == 1
    assert s.win_rate == round(2 / 3 * 100, 1)
    assert s.total_pnl == 300.0  # +200 -200 +300
    assert s.avg_profit == 250.0 and s.avg_loss == -200.0
    assert set(s.by_category) == {"day", "swing", "long"}
    assert s.monthly == {"2026-06": 300.0}


def test_stats_empty():
    s = compute_stats([])
    assert s.n_trades == 0 and s.win_rate is None and s.total_pnl == 0.0
