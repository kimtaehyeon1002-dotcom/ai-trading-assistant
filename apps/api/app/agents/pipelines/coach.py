"""Trading Coach 파이프라인 — 코드 메트릭 → Sonnet 교육형 해석 → 가드레일 → 면책. 설계서 §2.4.

개별 종목 권유·목표가 없이 행동 패턴+일반 리스크관리 교육만. "지금 다시 살까?"류는 교육+면책 라우팅.
정량 지표는 코드 계산(LLM 비의존), LLM은 해석만. 모든 산출물은 guard_research_output 통과.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.prompts import coach as P
from app.agents.prompts.research import stub_classification
from app.agents.router import Task
from app.compliance.disclaimers import DISCLAIMER_VERSION
from app.compliance.guard import guard_research_output
from app.schemas.journal import CoachBlocks, CoachResult, JournalMetrics
from app.services import journal_service


async def run_coach(
    session: AsyncSession, user_id: uuid.UUID, *, question: str | None = None
) -> CoachResult:
    metrics = await journal_service.compute_user_metrics(session, user_id)

    is_trade_decision = bool(stub_classification(question).get("is_trade_decision")) if question else False

    claude = get_claude()
    result = await claude.complete(
        Task.JOURNAL_ANALYSIS,
        system=P.coach_system(),
        messages=[
            {
                "role": "user",
                "content": P.build_coach_user(
                    metrics, question=question, is_trade_decision=is_trade_decision
                ),
            }
        ],
        max_tokens=1000,
    )
    raw_md = (
        P.stub_coach_markdown(metrics, is_trade_decision=is_trade_decision)
        if result.is_stub
        else result.text
    )
    await persist_agent_run(session, result, user_id=user_id)

    guard = await guard_research_output(raw_md, session=session, user_id=user_id)
    blocked = guard.blocked
    blocks = None if blocked else CoachBlocks(**P.parse_coach_blocks(raw_md))

    return CoachResult(
        status="blocked" if blocked else "completed",
        blocked=blocked,
        title="매매 회고 (교육형 코치)",
        markdown=guard.text,
        blocks=blocks,
        metrics=JournalMetrics(**metrics),
        is_trade_decision=is_trade_decision,
        disclaimer_version=DISCLAIMER_VERSION,
        model=result.model,
        cost_usd=float(result.cost_usd),
    )
