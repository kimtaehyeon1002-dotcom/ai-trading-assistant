"""시스템/디버그 라우터 — Claude 래퍼 핑(agent_run 비용 로깅 검증용)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.router import Task
from app.api.deps import get_current_user, require_admin
from app.core.db import get_session
from app.models.user import User
from app.services import rag_service

router = APIRouter(prefix="/debug", tags=["system"])


@router.post("/claude-ping")
async def claude_ping(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Haiku로 핑 → agent_run 적재. (ANTHROPIC_API_KEY 없으면 stub 모드로 로깅만 검증)"""
    result = await get_claude().complete(
        Task.PING,
        system="너는 한국어로 한 문장만 답하는 정보 보조다. 투자 권유는 하지 않는다.",
        messages=[{"role": "user", "content": "헬스체크: 'pong'이라고만 답해."}],
        max_tokens=16,
    )
    run = await persist_agent_run(session, result, user_id=user.user_id)
    return {
        "text": result.text,
        "is_stub": result.is_stub,
        "agent_run": {
            "run_id": str(run.run_id),
            "model": run.model,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "cost_usd": float(run.cost_usd),
            "latency_ms": run.latency_ms,
            "status": run.status,
        },
    }


@router.post("/rag-ingest-news")
async def rag_ingest_news(
    market: str | None = None,
    limit: int = 20,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """최근 뉴스를 RAG에 적재(제목+요약만, 본문 미저장). 설계서 §2.5/§5.

    VOYAGE_API_KEY 없으면 결정적 스텁 임베딩으로 인입 경로를 검증한다.
    """
    return await rag_service.ingest_news(session, market=market, limit=limit)
