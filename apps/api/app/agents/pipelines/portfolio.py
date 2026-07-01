"""포트폴리오 분석 파이프라인 — 코드 메트릭 → Sonnet 해석 → 가드레일 → 면책. 설계서 §2.4.

지표(비중·집중도·노출)는 코드 계산, LLM은 해석·시나리오만. 리밸런싱 지시 금지. guard fail-closed.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.prompts import portfolio as P
from app.agents.router import Task
from app.compliance.disclaimers import DISCLAIMER_VERSION
from app.compliance.guard import guard_research_output
from app.schemas.portfolio import PortfolioAnalysisResult, PortfolioBlocks, PortfolioMetrics
from app.services import portfolio_service


async def run_portfolio_analysis(
    session: AsyncSession, user_id: uuid.UUID
) -> PortfolioAnalysisResult:
    metrics, _outs, _note = await portfolio_service.compute(session, user_id)

    claude = get_claude()
    result = await claude.complete(
        Task.PORTFOLIO_ANALYSIS,
        system=P.portfolio_system(),
        messages=[{"role": "user", "content": P.build_portfolio_user(metrics)}],
        max_tokens=1000,
    )
    raw_md = P.stub_portfolio_markdown(metrics) if result.is_stub else result.text
    await persist_agent_run(session, result, user_id=user_id)

    guard = await guard_research_output(raw_md, session=session, user_id=user_id)
    blocked = guard.blocked
    blocks = None if blocked else PortfolioBlocks(**P.parse_portfolio_blocks(raw_md))

    return PortfolioAnalysisResult(
        status="blocked" if blocked else "completed",
        blocked=blocked,
        title="포트폴리오 분석 (분산 관점 관찰)",
        markdown=guard.text,
        blocks=blocks,
        metrics=PortfolioMetrics(**metrics),
        disclaimer_version=DISCLAIMER_VERSION,
        model=result.model,
        cost_usd=float(result.cost_usd),
    )
