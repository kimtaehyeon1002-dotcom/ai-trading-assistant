"""Provider 추상 인터페이스. 무료/유료 어댑터가 동일 정규화 스키마를 구현한다. (설계서 §1 L5)"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.data_providers.normalization import InstrumentRef
from app.schemas.market import CandleSeries, Financials, FxRate, NewsItem, Quote


class BaseProvider(ABC):
    name: str = "base"
    tier: str = "free"  # free | paid
    markets: tuple[str, ...] = ()  # ("KR",) | ("US",) | ("KR","US")
    is_realtime: bool = False
    priority: int = 100  # 낮을수록 우선

    def supports(self, market: str) -> bool:
        return market.upper() in self.markets


class QuoteProvider(BaseProvider):
    @abstractmethod
    async def get_quote(self, ref: InstrumentRef) -> Quote: ...

    async def get_candles(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        raise NotImplementedError


class FinancialsProvider(BaseProvider):
    @abstractmethod
    async def get_financials(
        self, ref: InstrumentRef, period_type: str, statement_type: str
    ) -> Financials: ...


class NewsProvider(BaseProvider):
    @abstractmethod
    async def get_news(
        self, market: str | None, symbols: list[str] | None, lang: str | None, limit: int
    ) -> list[NewsItem]: ...


class FxProvider(BaseProvider):
    @abstractmethod
    async def get_fx(self, base: str, quote: str) -> FxRate: ...
