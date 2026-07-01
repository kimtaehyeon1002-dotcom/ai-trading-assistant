"""시세/시장 dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Quote:
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    currency: str = ""
    source: str = "yfinance"

    @property
    def up(self) -> bool | None:
        if self.change_pct is None:
            return None
        return self.change_pct >= 0


@dataclass
class IndexQuote(Quote):
    """지수(가격 단위가 포인트)."""


@dataclass
class FxRate:
    base: str
    quote: str
    rate: float | None = None
    change_pct: float | None = None

    @property
    def pair(self) -> str:
        return f"{self.base}/{self.quote}"


@dataclass
class EconomicEvent:
    date: str  # YYYY-MM-DD
    time: str = ""  # HH:MM (KST) 또는 ""
    country: str = ""
    title: str = ""
    importance: str = "medium"  # low | medium | high


@dataclass
class MarketSummary:
    indices: list[IndexQuote] = field(default_factory=list)
    futures: list[Quote] = field(default_factory=list)
    fx: list[FxRate] = field(default_factory=list)
    watchlist: list[Quote] = field(default_factory=list)
    headline: str = ""  # 규칙 기반 한 줄 요약
