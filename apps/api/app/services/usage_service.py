"""사용량/쿼터 — agent_run 실측 비용 집계 + 요금제 쿼터 결정. 설계서 §1.4, §1.6.

일/사용자별 비용 대시보드의 백본인 agent_run을 집계해 일일 한도와 비교한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.plans import QuotaDecision, decide_quota, get_plan
from app.models.agent_run import AgentRun
from app.models.user import User


def _day_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def spent_today(session: AsyncSession, user_id: uuid.UUID) -> float:
    res = await session.execute(
        select(func.coalesce(func.sum(AgentRun.cost_usd), 0)).where(
            AgentRun.user_id == user_id, AgentRun.started_at >= _day_start_utc()
        )
    )
    return float(res.scalar_one() or 0.0)


async def _plan_name(session: AsyncSession, user_id: uuid.UUID) -> str:
    res = await session.execute(select(User.plan).where(User.user_id == user_id))
    return res.scalar_one_or_none() or "free"


async def get_usage(session: AsyncSession, user_id: uuid.UUID) -> dict:
    plan = get_plan(await _plan_name(session, user_id))
    spent = await spent_today(session, user_id)
    return {
        "plan": plan.name,
        "daily_cost_limit_usd": plan.daily_cost_limit_usd,
        "spent_today_usd": round(spent, 6),
        "remaining_usd": round(plan.daily_cost_limit_usd - spent, 6),
        "allow_deep": plan.allow_deep,
    }


async def enforce(
    session: AsyncSession, user_id: uuid.UUID, *, wants_deep: bool = False
) -> QuotaDecision:
    """현재 소비 + 요청 특성으로 쿼터 결정(allow|downgrade|block)."""
    plan = get_plan(await _plan_name(session, user_id))
    spent = await spent_today(session, user_id)
    return decide_quota(plan, spent, wants_deep=wants_deep)
