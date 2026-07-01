"""시장 라우터 — 종목/시세/캔들/뉴스/환율. 모든 응답에 Provider 메타 포함."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.schemas.market import CandleSeries, FxRate, NewsItem, Quote
from app.services import market_service

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/symbols")
async def search_symbols(
    q: str | None = None,
    market: str | None = Query(None, pattern="^(KR|US)$"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await market_service.search_symbols(session, q, market, limit)
    return {
        "data": [
            {
                "instrument_id": r.instrument_id,
                "symbol_norm": r.symbol_norm,
                "ticker": r.ticker,
                "market": r.market,
                "name": r.name_local or r.name_en,
                "exchange": r.exchange,
                "currency": r.currency,
            }
            for r in rows
        ]
    }


async def _require_instrument(session: AsyncSession, instrument_id: int):
    inst = await market_service.resolve_instrument(session, instrument_id=instrument_id)
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="instrument not found")
    return inst


@router.get("/quotes/{instrument_id}", response_model=Quote)
async def get_quote(
    instrument_id: int, session: AsyncSession = Depends(get_session)
) -> Quote:
    inst = await _require_instrument(session, instrument_id)
    return await market_service.get_quote(session, inst)


@router.get("/candles/{instrument_id}", response_model=CandleSeries)
async def get_candles(
    instrument_id: int,
    interval: str = Query("1d", pattern="^(1m|5m|1h|1d)$"),
    frm: str | None = Query(None, alias="from"),
    to: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> CandleSeries:
    inst = await _require_instrument(session, instrument_id)
    return await market_service.get_candles(session, inst, interval, frm, to)


@router.get("/news", response_model=list[NewsItem])
async def get_news(
    market: str | None = Query(None, pattern="^(KR|US)$"),
    lang: str | None = Query(None, pattern="^(ko|en)$"),
    limit: int = Query(20, ge=1, le=50),
) -> list[NewsItem]:
    return await market_service.get_news(market, None, lang, limit)


@router.get("/fx", response_model=FxRate)
async def get_fx(base: str = "USD", quote: str = "KRW") -> FxRate:
    return await market_service.get_fx(base, quote)
