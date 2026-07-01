"""매매일지 라우터 — Notion 임포트 + 조회 + 코드 메트릭 + Trading Coach. 설계서 §1.3-C, §7.2.

코치 분석은 매매습관·통계·관찰·교육 중심(추천 아님) + 면책. 매수/매도 추천·목표가 없음.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pipelines.coach import run_coach
from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.schemas.journal import (
    CoachRequest,
    CoachResult,
    ImportResult,
    JournalEntryOut,
    JournalMetrics,
)
from app.services import journal_service

router = APIRouter(prefix="/journal", tags=["journal"], dependencies=[Depends(get_current_user)])


@router.post("/import", response_model=ImportResult)
async def import_journal(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> ImportResult:
    """Notion 매매일지 → trade_journal_entry 적재(멱등). 토큰 없으면 스텁 픽스처."""
    return await journal_service.import_from_notion(session, user.user_id)


@router.get("/entries", response_model=list[JournalEntryOut])
async def list_entries(
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[JournalEntryOut]:
    entries = await journal_service.get_entries(session, user.user_id, limit=limit)
    return [
        JournalEntryOut(
            entry_id=str(e.entry_id),
            traded_on=e.traded_on,
            symbol=e.symbol,
            position=e.position,
            pnl=float(e.pnl) if e.pnl is not None else None,
            outcome=e.outcome,
            note=e.note,
        )
        for e in entries
    ]


@router.get("/metrics", response_model=JournalMetrics)
async def journal_metrics(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> JournalMetrics:
    """코드 계산 메트릭(LLM 비의존) — 승률·손익비·기대값·MDD·포지션/종목/요일 분해."""
    m = await journal_service.compute_user_metrics(session, user.user_id)
    return JournalMetrics(**m)


@router.post("/coach", response_model=CoachResult)
async def coach(
    req: CoachRequest | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CoachResult:
    """교육형 회고 — 코드 메트릭 + Sonnet 해석(가드레일 통과 + 면책). 매수/매도 권유 없음."""
    body = req or CoachRequest()
    return await run_coach(session, user.user_id, question=body.question)
