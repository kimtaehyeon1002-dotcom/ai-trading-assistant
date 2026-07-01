"""시장 도메인 서비스 — instrument 해소 + Provider 추상화 호출(정규화 응답)."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import InstrumentRef
from app.data_providers.registry import get_registry
from app.models.instrument import Instrument
from app.schemas.market import CandleSeries, FxRate, NewsItem, Quote


def _ref(inst: Instrument) -> InstrumentRef:
    return InstrumentRef(
        instrument_id=inst.instrument_id,
        market=inst.market,
        ticker=inst.ticker,
        symbol_norm=inst.symbol_norm,
        currency=inst.currency,
    )


async def resolve_instrument(
    session: AsyncSession, *, instrument_id: int | None = None, symbol: str | None = None
) -> Instrument | None:
    if instrument_id is not None:
        return await session.get(Instrument, instrument_id)
    if symbol:
        s = symbol.strip().upper()
        res = await session.execute(
            select(Instrument).where(
                or_(Instrument.symbol_norm == s, Instrument.ticker == s)
            )
        )
        return res.scalars().first()
    return None


async def search_symbols(
    session: AsyncSession, q: str | None, market: str | None, limit: int
) -> list[Instrument]:
    stmt = select(Instrument).where(Instrument.is_active.is_(True))
    if market:
        stmt = stmt.where(Instrument.market == market.upper())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Instrument.ticker.ilike(like),
                Instrument.symbol_norm.ilike(like),
                Instrument.name_local.ilike(like),
                Instrument.name_en.ilike(like),
            )
        )
    stmt = stmt.limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_quote(session: AsyncSession, inst: Instrument) -> Quote:
    return await get_registry().get_quote(_ref(inst))


async def get_candles(
    session: AsyncSession, inst: Instrument, interval: str, frm: str | None, to: str | None
) -> CandleSeries:
    return await get_registry().get_candles(_ref(inst), interval, frm, to)


async def get_news(
    market: str | None, symbols: list[str] | None, lang: str | None, limit: int
) -> list[NewsItem]:
    return await get_registry().get_news(market, symbols, lang, limit)


async def get_fx(base: str, quote: str) -> FxRate:
    return await get_registry().get_fx(base, quote)


__all__ = [
    "resolve_instrument",
    "search_symbols",
    "get_quote",
    "get_candles",
    "get_news",
    "get_fx",
    "SourceUnavailable",
]
