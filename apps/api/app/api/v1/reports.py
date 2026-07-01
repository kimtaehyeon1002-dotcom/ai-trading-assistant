"""모닝리포트 라우터 — 조회 + 테마 스코어 + 생성(admin). 설계서 §7.2.

생성은 비동기(202): 백그라운드 잡으로 공용 리포트를 만들고, by-date/{date}로 폴링 조회.
모든 응답은 면책 포함(markdown에 부착됨). 매수/매도 추천 없음.
"""
from __future__ import annotations

import asyncio
import uuid as _uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pipelines.morning_report import generate_morning_report
from app.analytics.theme_scoring import engine as theme_engine
from app.api.deps import get_current_user, require_admin
from app.core.db import SessionLocal, get_session
from app.data_providers.normalization import now_utc
from app.models.morning_report import MorningReport
from app.models.user import User
from app.schemas.report import (
    GenerateReportRequest,
    GenerateReportResponse,
    MorningReportOut,
    ReportListItem,
    ThemeScoreOut,
)

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])

# 백그라운드 잡 강참조 보관(GC 방지) — 단일 프로세스 MVP. Phase 7에서 Celery로 이관.
_bg_tasks: set[asyncio.Task] = set()


def _to_out(r: MorningReport) -> MorningReportOut:
    return MorningReportOut(
        report_id=str(r.report_id),
        report_date=r.report_date,
        scope=r.scope,
        version=r.version,
        status=r.status,
        blocked=r.blocked,
        markdown=r.markdown,
        sections=r.sections,
        model=r.model,
        cost_usd=float(r.cost_usd),
        disclaimer_version=r.disclaimer_version,
        created_at=r.created_at,
    )


@router.get("", response_model=list[ReportListItem])
async def list_reports(
    limit: int = Query(20, ge=1, le=100), session: AsyncSession = Depends(get_session)
) -> list[ReportListItem]:
    rows = (
        await session.execute(
            select(MorningReport).order_by(MorningReport.report_date.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        ReportListItem(
            report_id=str(r.report_id),
            report_date=r.report_date,
            scope=r.scope,
            status=r.status,
            blocked=r.blocked,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/themes", response_model=list[ThemeScoreOut])
async def latest_theme_scores(
    market: str = Query(..., pattern="^(KR|US)$"),
    timeframe: str = Query("swing"),
    top_k: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[ThemeScoreOut]:
    scores = await theme_engine.get_latest_scores(
        session, market=market.upper(), timeframe=timeframe, top_k=top_k
    )
    return [ThemeScoreOut(**s) for s in scores]


@router.get("/by-date/{report_date}", response_model=MorningReportOut)
async def get_report_by_date(
    report_date: date_type,
    scope: str = Query("global"),
    session: AsyncSession = Depends(get_session),
) -> MorningReportOut:
    res = await session.execute(
        select(MorningReport).where(
            MorningReport.report_date == report_date,
            MorningReport.scope == scope,
            MorningReport.version == 1,
        )
    )
    report = res.scalars().first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return _to_out(report)


@router.get("/{report_id}", response_model=MorningReportOut)
async def get_report(report_id: str, session: AsyncSession = Depends(get_session)) -> MorningReportOut:
    try:
        rid = _uuid.UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found") from exc
    report = await session.get(MorningReport, rid)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return _to_out(report)


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, response_model=GenerateReportResponse)
async def generate_report(
    req: GenerateReportRequest | None = None, _admin: User = Depends(require_admin)
) -> GenerateReportResponse:
    body = req or GenerateReportRequest()
    rdate = body.report_date or now_utc().date()

    async def _run() -> None:
        async with SessionLocal() as session:
            await generate_morning_report(session, report_date=rdate, force=body.force)

    task = asyncio.create_task(_run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return GenerateReportResponse(report_date=rdate, scope="global", status="accepted")
