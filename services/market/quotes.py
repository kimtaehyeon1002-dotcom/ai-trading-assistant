"""워치리스트/지수 시세."""
from __future__ import annotations

from config.markets import INDICES, WATCHLIST
from models.market import IndexQuote, Quote
from services.market._yf import fast_quote


def get_watchlist() -> list[Quote]:
    out: list[Quote] = []
    for region, items in WATCHLIST.items():
        currency = "KRW" if region == "KR" else "USD"
        for symbol, name in items:
            price, change = fast_quote(symbol)
            out.append(Quote(symbol=symbol, name=name, price=price, change_pct=change, currency=currency))
    return out


def get_indices() -> list[IndexQuote]:
    out: list[IndexQuote] = []
    for symbol, name in INDICES:
        price, change = fast_quote(symbol)
        out.append(IndexQuote(symbol=symbol, name=name, price=price, change_pct=change))
    return out
