"""선물 시세."""
from __future__ import annotations

from config.markets import FUTURES
from models.market import Quote
from services.market._yf import fast_quote


def get_futures() -> list[Quote]:
    out: list[Quote] = []
    for symbol, name in FUTURES:
        price, change = fast_quote(symbol)
        out.append(Quote(symbol=symbol, name=name, price=price, change_pct=change))
    return out
