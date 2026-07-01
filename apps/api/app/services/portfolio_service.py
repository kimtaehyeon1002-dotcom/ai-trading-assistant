"""포트폴리오 서비스 — 보유 CRUD + 다통화 평가 + 코드 메트릭. 설계서 §2.4.

평가액은 시세×수량을 기준통화로 환산(시세 미수집 시 평단가 폴백). 비중·집중도·노출은
analytics.portfolio_metrics(LLM 비의존)로 계산. 리밸런싱 '지시'는 하지 않는다(관찰 지표만).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.portfolio_metrics import Position, compute_portfolio_metrics
from app.core.logging import get_logger
from app.data_providers.errors import ProviderError
from app.models.instrument import Instrument
from app.models.portfolio import Holding, Portfolio
from app.schemas.portfolio import HoldingIn, HoldingOut
from app.services import market_service

log = get_logger("portfolio")


async def get_or_create_default(session: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    res = await session.execute(
        select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at).limit(1)
    )
    pf = res.scalars().first()
    if pf is None:
        pf = Portfolio(user_id=user_id)
        session.add(pf)
        await session.commit()
        await session.refresh(pf)
    return pf


async def _rows(session: AsyncSession, portfolio_id: uuid.UUID) -> list[tuple[Holding, Instrument]]:
    res = await session.execute(
        select(Holding, Instrument)
        .join(Instrument, Holding.instrument_id == Instrument.instrument_id)
        .where(Holding.portfolio_id == portfolio_id)
    )
    return [(h, i) for h, i in res.all()]


async def add_holding(session: AsyncSession, user_id: uuid.UUID, body: HoldingIn) -> Holding:
    inst = await market_service.resolve_instrument(
        session, instrument_id=body.instrument_id, symbol=body.symbol
    )
    if inst is None:
        raise ValueError("instrument not found")
    pf = await get_or_create_default(session, user_id)
    existing = await session.execute(
        select(Holding).where(
            Holding.portfolio_id == pf.portfolio_id, Holding.instrument_id == inst.instrument_id
        )
    )
    h = existing.scalars().first()
    if h is None:
        h = Holding(
            portfolio_id=pf.portfolio_id,
            instrument_id=inst.instrument_id,
            quantity=Decimal(str(body.quantity)),
            avg_cost=Decimal(str(body.avg_cost)) if body.avg_cost is not None else None,
        )
        session.add(h)
    else:
        h.quantity = Decimal(str(body.quantity))
        if body.avg_cost is not None:
            h.avg_cost = Decimal(str(body.avg_cost))
    await session.commit()
    await session.refresh(h)
    return h


async def delete_holding(session: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> bool:
    pf = await get_or_create_default(session, user_id)
    res = await session.execute(
        select(Holding).where(
            Holding.holding_id == holding_id, Holding.portfolio_id == pf.portfolio_id
        )
    )
    h = res.scalars().first()
    if h is None:
        return False
    await session.delete(h)
    await session.commit()
    return True


def _fx_factor(currency: str | None, base: str, usdkrw: float | None) -> float | None:
    """종목 통화 → 기준통화 환산 계수."""
    if not currency:
        return None
    if currency == base:
        return 1.0
    if usdkrw is None:
        return None
    if currency == "USD" and base == "KRW":
        return usdkrw
    if currency == "KRW" and base == "USD":
        return 1.0 / usdkrw if usdkrw else None
    return None  # 미지원 통화쌍 → 평가 제외(플래그)


async def compute(session: AsyncSession, user_id: uuid.UUID) -> tuple[dict, list[HoldingOut], str | None]:
    pf = await get_or_create_default(session, user_id)
    rows = await _rows(session, pf.portfolio_id)
    base = pf.base_currency

    usdkrw = None
    try:
        fx = await market_service.get_fx("USD", "KRW")
        usdkrw = fx.rate
    except ProviderError:
        usdkrw = None

    positions: list[Position] = []
    outs: list[HoldingOut] = []
    degraded = 0
    for h, inst in rows:
        qty = float(h.quantity)
        avg_cost = float(h.avg_cost) if h.avg_cost is not None else None
        price = None
        try:
            q = await market_service.get_quote(session, inst)
            price = q.price
        except ProviderError:
            price = None

        factor = _fx_factor(inst.currency, base, usdkrw)
        basis = "none"
        value_base = None
        unit_price = price if price is not None else avg_cost
        if unit_price is not None and factor is not None:
            value_base = qty * unit_price * factor
            basis = "market" if price is not None else "cost"
        if basis != "market":
            degraded += 1

        positions.append(
            Position(
                symbol=inst.symbol_norm,
                value_base=value_base or 0.0,
                sector=inst.sector,
                market=inst.market,
                currency=inst.currency,
            )
        )
        outs.append(
            HoldingOut(
                holding_id=str(h.holding_id),
                instrument_id=inst.instrument_id,
                symbol_norm=inst.symbol_norm,
                name=inst.name_local or inst.name_en,
                market=inst.market,
                currency=inst.currency,
                quantity=qty,
                avg_cost=avg_cost,
                price=price,
                value_base=round(value_base, 2) if value_base is not None else None,
                valuation_basis=basis,
            )
        )

    metrics = compute_portfolio_metrics(positions, base_currency=base)
    weight_by_symbol = {p["symbol"]: p["weight"] for p in metrics["positions"]}
    for o in outs:
        o.weight = weight_by_symbol.get(o.symbol_norm)

    note = None
    if degraded:
        note = f"{degraded}개 종목은 시세 미수집으로 평단가/제외 처리됨(환율 {'있음' if usdkrw else '없음'})."
    metrics["valuation_note"] = note
    return metrics, outs, note
