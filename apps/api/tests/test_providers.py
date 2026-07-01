"""Provider 폴백 계약 테스트 — 실패 어댑터 → 다음 우선순위로 폴백."""
import pytest

from app.data_providers.base import QuoteProvider
from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import InstrumentRef, now_utc
from app.data_providers.registry import ProviderRegistry
from app.schemas.market import ProviderMeta, Quote

REF = InstrumentRef(instrument_id=1, market="US", ticker="AAPL", symbol_norm="AAPL", currency="USD")


class FailingProvider(QuoteProvider):
    name = "failing"
    markets = ("US",)
    priority = 10

    async def get_quote(self, ref: InstrumentRef) -> Quote:
        raise SourceUnavailable("boom")


class GoodProvider(QuoteProvider):
    name = "good"
    markets = ("US",)
    priority = 20

    async def get_quote(self, ref: InstrumentRef) -> Quote:
        return Quote(
            instrument_id=ref.instrument_id,
            symbol_norm=ref.symbol_norm,
            market=ref.market,
            currency=ref.currency,
            price=190.0,
            meta=ProviderMeta(source=self.name, as_of=now_utc()),
        )


async def test_fallback_to_next_provider():
    reg = ProviderRegistry()
    reg.quote = [FailingProvider(), GoodProvider()]
    q = await reg.get_quote(REF)
    assert q.price == 190.0
    assert q.meta.source == "good"


async def test_all_fail_raises_source_unavailable():
    reg = ProviderRegistry()
    reg.quote = [FailingProvider()]
    with pytest.raises(SourceUnavailable):
        await reg.get_quote(REF)


async def test_market_filtering():
    reg = ProviderRegistry()
    reg.quote = [GoodProvider()]  # US only
    kr_ref = InstrumentRef(
        instrument_id=2, market="KR", ticker="005930", symbol_norm="005930.KS", currency="KRW"
    )
    with pytest.raises(SourceUnavailable):
        await reg.get_quote(kr_ref)
