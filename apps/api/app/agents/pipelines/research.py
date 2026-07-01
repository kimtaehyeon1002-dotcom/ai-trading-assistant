"""리서치 파이프라인 — Haiku 의도분류 → 코드 기반 툴 수집 → Sonnet/Opus 4-블록 스트리밍
합성 → 문장 단위 가드레일 게이트 → 풀 검증 + 면책 → research_report 영속화.

설계서 §1.3-B, §2.1(결정적 코드 오케스트레이션), §2.4, §2.6. 모든 LLM 호출은 agent_run 로깅.
push(event, data): SSE 콜백 — stage | tool | token | done | error.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.prompts import research as P
from app.agents.router import Task
from app.agents.streaming_gate import SentenceGate
from app.agents.tools.definitions import gather_context
from app.compliance.disclaimers import DISCLAIMER_VERSION
from app.compliance.guard import guard_research_output
from app.core.config import settings
from app.core.logging import get_logger
from app.data_providers.normalization import now_utc
from app.models.research_report import ResearchReport
from app.schemas.research import (
    Citation,
    IntentClassification,
    ResearchBlocks,
    ResearchRequest,
    ResearchResult,
)
from app.services import market_service

log = get_logger("research_pipeline")

PushFn = Callable[[str, object], Awaitable[None]]


async def run_research_pipeline(
    session: AsyncSession,
    user_id: uuid.UUID,
    job_id: str,
    request: ResearchRequest,
    push: PushFn,
) -> ResearchResult:
    claude = get_claude()

    # ── 1) 의도분류 (Haiku) ──
    await push("stage", {"stage": "classify", "label": "의도 분류"})
    intent = await _classify(session, user_id, request)
    await push(
        "stage",
        {"stage": "classified", "intent": intent.intent, "is_trade_decision": intent.is_trade_decision},
    )

    # ── 2) 종목 해소 + 툴 수집 ──
    inst = await market_service.resolve_instrument(
        session,
        instrument_id=request.instrument_id,
        symbol=request.symbol or (intent.instruments[0] if intent.instruments else None),
    )
    ctx: dict = {
        "query": request.query,
        "style": request.style,
        "is_trade_decision": intent.is_trade_decision,
    }
    citations: list[Citation] = []
    if inst is None:
        await push("stage", {"stage": "no_instrument", "label": "종목 미특정"})
        ctx.update({"name": None, "symbol_norm": request.symbol, "market": request.market})
    else:
        ctx.update(
            {
                "name": inst.name_local or inst.name_en,
                "symbol_norm": inst.symbol_norm,
                "market": inst.market,
            }
        )
        # 비용 절감: 같은 종목·질문·당일 완료 리포트가 있으면 LLM 없이 재사용
        if settings.research_cache_same_day:
            cached = await _todays_report(session, user_id, inst.instrument_id, request)
            if cached is not None:
                await push("stage", {"stage": "cache_hit", "label": "당일 캐시 재사용"})
                result = _result_from_report(cached, job_id)
                await push(
                    "done",
                    {
                        "job_id": job_id,
                        "report_id": str(cached.report_id),
                        "status": cached.status,
                        "blocked": cached.blocked,
                        "cached": True,
                        "result_url": f"/api/v1/research/results/{cached.report_id}",
                    },
                )
                log.info("research_cache_hit", job_id=job_id, report_id=str(cached.report_id))
                return result
        await push("stage", {"stage": "gather", "label": "데이터 수집"})
        gathered = await gather_context(
            session, inst, push, query=request.query, user_id=user_id
        )
        ctx.update(gathered["ctx"])
        citations = gathered["citations"]

    # ── 3) 합성 (Sonnet/Opus) + 문장 게이트 스트리밍 ──
    await push("stage", {"stage": "synthesize", "label": "리포트 합성"})
    task = Task.RESEARCH_DEEP if request.depth == "deep" else Task.RESEARCH
    system = P.synthesis_system()
    user_msg = P.build_user_message(ctx)
    stub_md = P.stub_research_markdown(ctx)

    gate = SentenceGate()
    streamed_parts: list[str] = []
    synth_result = None
    async for ev in claude.stream(
        task,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=1024,
        stub_text=stub_md,
    ):
        if ev["type"] == "text":
            for emission in gate.feed(ev["text"]):
                streamed_parts.append(emission.text)
                await push("token", {"t": emission.text})
        elif ev["type"] == "final":
            synth_result = ev["result"]
    for emission in gate.flush():
        streamed_parts.append(emission.text)
        await push("token", {"t": emission.text})

    # 합성 호출 비용 로깅(agent_run)
    run = None
    if synth_result is not None:
        run = await persist_agent_run(session, synth_result, user_id=user_id)

    streamed_md = "".join(streamed_parts)

    # ── 4) 풀 가드레일(규칙 + 2차 LLM) + 면책 ──
    await push("stage", {"stage": "guard", "label": "컴플라이언스 검증"})
    guard = await guard_research_output(streamed_md, session=session, user_id=user_id)
    blocked = guard.blocked
    final_md = guard.text  # 통과: 본문+면책 / 차단: 중립 안내+면책
    status = "blocked" if blocked else "completed"
    blocks = None if blocked else ResearchBlocks(**P.parse_blocks(streamed_md))

    title = f"{ctx.get('name') or ctx.get('symbol_norm') or '종목'} 리서치"

    # ── 5) 영속화(감사) ──
    report = ResearchReport(
        user_id=user_id,
        instrument_id=inst.instrument_id if inst else None,
        title=title,
        query=request.query,
        style=request.style,
        depth=request.depth,
        status=status,
        blocked=blocked,
        markdown=final_md,
        blocks=blocks.model_dump() if blocks else None,
        citations=[c.model_dump(mode="json") for c in citations],
        intent=intent.model_dump(),
        model=synth_result.model if synth_result else None,
        cost_usd=(synth_result.cost_usd if synth_result else 0),
        agent_run_id=run.run_id if run else None,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    result = ResearchResult(
        job_id=job_id,
        status=status,
        blocked=blocked,
        instrument_id=inst.instrument_id if inst else None,
        symbol_norm=ctx.get("symbol_norm"),
        title=title,
        markdown=final_md,
        blocks=blocks,
        citations=citations,
        disclaimer_version=DISCLAIMER_VERSION,
        intent=intent,
        model=synth_result.model if synth_result else None,
        cost_usd=float(synth_result.cost_usd) if synth_result else 0.0,
        created_at=report.created_at,
    )
    await push(
        "done",
        {
            "job_id": job_id,
            "report_id": str(report.report_id),
            "status": status,
            "blocked": blocked,
            "redacted_sentences": gate.redacted_count,
            "result_url": f"/api/v1/research/results/{report.report_id}",
        },
    )
    if gate.redacted_count:
        log.info("research_gate_redacted", job_id=job_id, count=gate.redacted_count, categories=gate.categories)
    return result


async def _classify(
    session: AsyncSession, user_id: uuid.UUID, request: ResearchRequest
) -> IntentClassification:
    """Haiku 의도분류. 스텁/파싱 실패 시 결정적 규칙 분류로 폴백. 항상 agent_run 로깅."""
    claude = get_claude()
    fallback = request.symbol
    result = await claude.complete(
        Task.CLASSIFY,
        system=P.CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": request.query or (request.symbol or "")}],
        max_tokens=200,
    )
    await persist_agent_run(session, result, user_id=user_id)

    data = None if result.is_stub else P.parse_classification(result.text)
    if not data:
        data = P.stub_classification(request.query, fallback_symbol=fallback)
    if not data.get("instruments") and fallback:
        data["instruments"] = [fallback]
    return IntentClassification(
        intent=data.get("intent", "research"),
        instruments=data.get("instruments") or [],
        is_trade_decision=bool(data.get("is_trade_decision")),
        timeframe=data.get("timeframe"),
        language=data.get("language", request.language),
    )


async def _todays_report(
    session: AsyncSession, user_id: uuid.UUID, instrument_id: int, request: ResearchRequest
) -> ResearchReport | None:
    """같은 종목·depth·질문으로 '오늘' 생성된 완료 리포트(비차단)를 재사용 후보로 반환."""
    day_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        (
            await session.execute(
                select(ResearchReport)
                .where(
                    ResearchReport.user_id == user_id,
                    ResearchReport.instrument_id == instrument_id,
                    ResearchReport.depth == request.depth,
                    ResearchReport.status == "completed",
                    ResearchReport.blocked.is_(False),
                    ResearchReport.created_at >= day_start,
                )
                .order_by(ResearchReport.created_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    for r in rows:
        if (r.query or None) == (request.query or None):
            return r
    return None


def _result_from_report(r: ResearchReport, job_id: str) -> ResearchResult:
    blocks = ResearchBlocks(**r.blocks) if r.blocks else None
    citations = [Citation(**c) for c in (r.citations or [])]
    intent = IntentClassification(**r.intent) if r.intent else None
    return ResearchResult(
        job_id=job_id,
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
