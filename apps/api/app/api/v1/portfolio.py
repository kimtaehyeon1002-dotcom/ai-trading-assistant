"""포트폴리오 라우터 — 보유 CRUD + 코드 메트릭 + 분산 관점 분석. 설계서 §2.4, §7.2.

분석은 분산 개념·관찰 포인트 중심(리밸런싱/매매 '지시' 없음) + 면책.
"""
from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pipelines.portfolio import run_portfolio_analysis
from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.schemas.portfolio import (
    HoldingIn,
    HoldingOut,
    PortfolioAnalysisResult,
    PortfolioMetrics,
)
from app.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


@router.get("/holdings", response_model=list[HoldingOut])
async def list_holdings(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[HoldingOut]:
    _metrics, outs, _note = await portfolio_service.compute(session, user.user_id)
    return outs


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
async def add_holding(
    body: HoldingIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        h = await portfolio_service.add_holding(session, user.user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "holding_id": str(h.holding_id),
        "instrument_id": h.instrument_id,
        "quantity": float(h.quantity),
        "avg_cost": float(h.avg_cost) if h.avg_cost is not None else None,
    }


@router.delete("/holdings/{holding_id}")
async def delete_holding(
    holding_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        hid = _uuid.UUID(holding_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="holding not found") from exc
    ok = await portfolio_service.delete_holding(session, user.user_id, hid)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="holding not found")
    return {"ok": True}


@router.get("/metrics", response_model=PortfolioMetrics)
async def portfolio_metrics(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> PortfolioMetrics:
    """코드 계산 메트릭(LLM 비의존) — 비중·HHI·유효종목수·섹터/시장/통화 노출."""
    metrics, _outs, _note = await portfolio_service.compute(session, user.user_id)
    return PortfolioMetrics(**metrics)


@router.post("/analyze", response_model=PortfolioAnalysisResult)
async def analyze_portfolio(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> PortfolioAnalysisResult:
    """분산 관점 분석 — 코드 메트릭 + Sonnet 해석(가드레일 통과 + 면책). 리밸런싱 지시 없음."""
    return await run_portfolio_analysis(session, user.user_id)
