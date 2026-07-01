"""Provider 레지스트리 — 시장/도메인별로 priority 순서로 폴백(무료↔유료).

유료 어댑터(KIS/Polygon/Finnhub)는 동일 인터페이스로 등록만 하면
상위 서비스 변경 없이 priority 조정으로 전환된다(설계서 §1.4, §9-E).
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.data_providers.base import FxProvider, NewsProvider, QuoteProvider
from app.data_providers.errors import ProviderError, SourceUnavailable
from app.data_providers.fx.yfinance_fx_provider import YFinanceFxProvider
from app.data_providers.kr.fdr_provider import FdrProvider
from app.data_providers.news.rss_provider import RssNewsProvider
from app.data_providers.normalization import InstrumentRef
from app.data_providers.us.yfinance_provider import YFinanceProvider
from app.schemas.market import CandleSeries, FxRate, NewsItem, Quote

log = get_logger("providers")


class ProviderRegistry:
    def __init__(self) -> None:
        self.quote: list[QuoteProvider] = []
        self.news: list[NewsProvider] = []
        self.fx: list[FxProvider] = []

    def register_defaults(self) -> "ProviderRegistry":
        # 무료 어댑터 기본 등록 (유료는 추후 동일 방식)
        self.quote = sorted([FdrProvider(), YFinanceProvider()], key=lambda p: p.priority)
        self.news = sorted([RssNewsProvider()], key=lambda p: p.priority)
        self.fx = sorted([YFinanceFxProvider()], key=lambda p: p.priority)
        return self

    async def get_quote(self, ref: InstrumentRef) -> Quote:
        return await self._fallback(
            [p for p in self.quote if p.supports(ref.market)],
            lambda p: p.get_quote(ref),
            f"quote {ref.symbol_norm}",
        )

    async def get_candles(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        return await self._fallback(
            [p for p in self.quote if p.supports(ref.market)],
            lambda p: p.get_candles(ref, interval, frm, to),
            f"candles {ref.symbol_norm}",
        )

    async def get_news(
        self, market: str | None, symbols: list[str] | None, lang: str | None, limit: int
    ) -> list[NewsItem]:
        return await self._fallback(
            self.news, lambda p: p.get_news(market, symbols, lang, limit), "news"
        )

    async def get_fx(self, base: str, quote: str) -> FxRate:
        return await self._fallback(self.fx, lambda p: p.get_fx(base, quote), f"fx {base}{quote}")

    async def _fallback(self, providers, call, what: str):
        last: Exception | None = None
        for p in providers:
            try:
                return await call(p)
            except ProviderError as exc:
                last = exc
                log.warning("provider_fallback", provider=p.name, what=what, error=str(exc))
                continue
        raise SourceUnavailable(f"all providers failed for {what}: {last}")


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry().register_defaults()
    return _registry
