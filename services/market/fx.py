"""환율(yfinance FX 심볼 USDKRW=X 등)."""
from __future__ import annotations

from config.markets import FX_PAIRS
from models.market import FxRate
from services.market._yf import fast_quote


def get_fx() -> list[FxRate]:
    out: list[FxRate] = []
    for base, quote in FX_PAIRS:
        rate, change = fast_quote(f"{base}{quote}=X")
        out.append(FxRate(base=base, quote=quote, rate=rate, change_pct=change))
    return out
