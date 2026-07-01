"""모닝리포트 파이프라인 — 공용 유니버스 1회 수집 → 테마 스코어 → Opus 합성 → 가드레일 → 적재.

설계서 §1.3-A, §2.5. 멱등(report_date+scope+version). 종목별 Sonnet Batch 1차 분석은 후속
최적화로 두고, MVP는 집계 데이터에 대한 단일 Opus 합성(스텁 가능)으로 5-섹션을 생성한다.
모든 LLM 산출물은 guard_research_output 통과 + 면책. 뉴스 본문 미저장.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.prompts import morning_report as P
from app.agents.router import Task
from app.analytics.theme_scoring import engine as theme_engine
from app.compliance.disclaimers import DISCLAIMER_VERSION
from app.core.config import settings
from app.compliance.guard import guard_research_output
from app.core.logging import get_logger
from app.data_providers.errors import ProviderError
from app.data_providers.normalization import now_utc
from app.models.morning_report import MorningReport
from app.rag.embeddings import content_hash
from app.services import market_service

log = get_logger("morning_report")


async def _get_existing(session: AsyncSession, report_date: date, scope: str) -> MorningReport | None:
    res = await session.execute(
        select(MorningReport).where(
            MorningReport.report_date == report_date,
            MorningReport.scope == scope,
            MorningReport.version == 1,
        )
    )
    return res.scalars().first()


async def generate_morning_report(
    session: AsyncSession,
    *,
    report_date: date | None = None,
    scope: str = "global",
    timeframe: str | None = None,
    force: bool = False,
) -> MorningReport:
    rdate = report_date or now_utc().date()
    existing = await _get_existing(session, rdate, scope)
    if existing is not None and not force:
        log.info("morning_report_idempotent_hit", date=str(rdate), scope=scope)
        return existing

    # ── 공용 유니버스 1회 수집 ──
    ctx: dict = {"report_date": rdate.isoformat()}

    try:
        fx = await market_service.get_fx("USD", "KRW")
        ctx["fx"] = {"rate": fx.rate, "source": fx.meta.source, "as_of": fx.meta.as_of.isoformat()}
    except ProviderError:
        ctx["fx"] = None

    # 테마 스코어(코드 계산) — 사용자 기준값: 시장/스타일/임계/상위N
    tf = timeframe or settings.morning_style
    top_n = settings.morning_top_themes
    min_score = settings.morning_min_theme_score
    markets = settings.morning_markets_list

    async def themes_for(market: str) -> list[dict]:
        if market not in markets:
            return []
        try:
            res = await theme_engine.compute_theme_scores(session, market=market, timeframe=tf)
        except Exception:  # noqa: BLE001
            return []
        picked = [r for r in res if r.score >= min_score][:top_n]
        return [{"theme": r.key, "score": r.score, "rank": r.rank} for r in picked]

    ctx["themes_us"] = await themes_for("US")
    ctx["themes_kr"] = await themes_for("KR")
    ctx["criteria"] = {
        "style": tf,
        "markets": markets,
        "top_themes": top_n,
        "min_theme_score": min_score,
    }

    try:
        news = await market_service.get_news(None, None, None, 5)
        ctx["news"] = [
            {"title": n.title, "source": n.source_name, "published_at": n.published_at.isoformat()}
            for n in news[:5]
        ]
    except ProviderError:
        ctx["news"] = []

    # ── 합성(Opus, 스텁 가능) ──
    claude = get_claude()
    # 비용 최소화: 기본 Sonnet 합성(morning_use_opus=True일 때만 Opus 심층)
    synth_task = Task.MORNING_REPORT if settings.morning_use_opus else Task.RESEARCH
    result = await claude.complete(
        synth_task,
        system=P.morning_system(),
        messages=[{"role": "user", "content": P.build_morning_user(ctx)}],
        max_tokens=1200,
    )
    raw_md = P.stub_morning_markdown(ctx) if result.is_stub else result.text
    run = await persist_agent_run(session, result)

    # ── 가드레일 + 면책 ──
    guard = await guard_research_output(raw_md, session=session)
    blocked = guard.blocked
    final_md = guard.text
    status = "blocked" if blocked else "completed"

    report = MorningReport(
        report_date=rdate,
        scope=scope,
        version=1,
        content_hash=content_hash(f"{rdate}|{scope}|{result.model}|{raw_md}"),
        sections={
            "fx": ctx.get("fx"),
            "themes_us": ctx.get("themes_us"),
            "themes_kr": ctx.get("themes_kr"),
            "news": ctx.get("news"),
        },
        markdown=final_md,
        status=status,
        blocked=blocked,
        model=result.model,
        cost_usd=result.cost_usd,
        agent_run_id=run.run_id,
        disclaimer_version=DISCLAIMER_VERSION,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    log.info("morning_report_generated", date=str(rdate), scope=scope, blocked=blocked)
    return report
