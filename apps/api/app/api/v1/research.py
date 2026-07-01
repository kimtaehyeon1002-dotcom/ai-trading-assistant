"""AI Research 라우터 — 비동기 Job + SSE 스트리밍 + 결과 조회. 설계서 §1.3-B, §7.2.

흐름: POST /jobs(202) → GET /jobs/{id}/stream(SSE) 또는 GET /jobs/{id}(폴링)
     → GET /results/{id}(멱등 재조회). 가드레일은 파이프라인 내부 단일 통과 지점에서 강제.
"""
from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_sse
from app.core.db import get_session
from app.core.sse import SSE_HEADERS, sse_event
from app.models.research_report import ResearchReport
from app.models.user import User
from app.schemas.research import (
    Citation,
    IntentClassification,
    JobEnvelope,
    JobStatus,
    NoteIn,
    ResearchBlocks,
    ResearchRequest,
    ResearchResult,
)
from app.services import rag_service, usage_service
from app.services.research_service import get_job_manager

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=JobEnvelope)
async def create_research_job(
    req: ResearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobEnvelope:
    if not (req.instrument_id or req.symbol or req.query):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="instrument_id, symbol, query 중 하나는 필요합니다.",
        )
    # 쿼터: 한도 초과 차단(429), 심층(Opus) 한도 부족 시 표준으로 강등
    decision = await usage_service.enforce(
        session, user.user_id, wants_deep=(req.depth == "deep")
    )
    if decision.action == "block":
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=decision.reason)
    if decision.action == "downgrade":
        req.depth = "standard"
    job = get_job_manager().create(user.user_id, req)
    return JobEnvelope(
        job_id=job.job_id,
        status=job.status,
        stream_url=f"/api/v1/research/jobs/{job.job_id}/stream",
        result_url=f"/api/v1/research/results/{job.job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_research_job(job_id: str, user: User = Depends(get_current_user)) -> JobStatus:
    job = get_job_manager().get(job_id)
    if job is None or job.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return JobStatus(
        job_id=job_id,
        status=job.status,
        error=job.error,
        result_url=f"/api/v1/research/results/{job_id}",
    )


@router.get("/jobs/{job_id}/stream")
async def stream_research_job(job_id: str, user: User = Depends(get_current_user_sse)):
    mgr = get_job_manager()
    job = mgr.get(job_id)
    if job is None or job.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    async def gen():
        yield sse_event("stage", {"stage": "connected", "job_id": job_id})
        async for event, data in mgr.events(job):
            yield sse_event(event, data)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def add_note(
    body: NoteIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """개인 노트를 RAG에 인입(본인만 검색됨). 리서치 합성 시 owner 필터로 surface."""
    return await rag_service.ingest_note(
        session,
        user.user_id,
        title=body.title,
        text=body.text,
        symbols=body.symbols,
        market=body.market,
    )


@router.get("/results/{result_id}", response_model=ResearchResult)
async def get_research_result(
    result_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ResearchResult:
    # 1) 인메모리 잡(job_id = hex32)
    job = get_job_manager().get(result_id)
    if job is not None:
        if job.user_id != user.user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result not found")
        if job.result is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"job status: {job.status}"
            )
        return job.result

    # 2) 영속 리포트(report_id = UUID)
    try:
        rid = _uuid.UUID(result_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="result not found"
        ) from exc
    report = await session.get(ResearchReport, rid)
    if report is None or (report.user_id and report.user_id != user.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="result not found")
    return _report_to_result(report)


def _report_to_result(r: ResearchReport) -> ResearchResult:
    blocks = ResearchBlocks(**r.blocks) if r.blocks else None
    citations = [Citation(**c) for c in (r.citations or [])]
    intent = IntentClassification(**r.intent) if r.intent else None
    return ResearchResult(
        job_id=str(r.report_id),
        status=r.status,
        blocked=r.blocked,
        instrument_id=r.instrument_id,
        symbol_norm=None,
        title=r.title,
        markdown=r.markdown,
        blocks=blocks,
        citations=citations,
        disclaimer_version=r.disclaimer_version or "",
        intent=intent,
        model=r.model,
        cost_usd=float(r.cost_usd),
        created_at=r.created_at,
    )
