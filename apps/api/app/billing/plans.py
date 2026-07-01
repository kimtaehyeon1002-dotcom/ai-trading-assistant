"""요금제 + 쿼터 결정 — 순수 로직(stdlib만). 설계서 §1.4 비용 티어링·쿼터.

일일 비용 상한 초과 → 차단(block), 심층(Opus) 제한/잔액 부족 → 표준 강등(downgrade).
agent_run 실측 비용으로 집계(usage_service)하고 여기서 결정만 한다(테스트 가능).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    name: str
    daily_cost_limit_usd: float  # 일일 LLM 비용 상한
    allow_deep: bool  # Opus 심층(RESEARCH_DEEP) 허용
    monthly_price_usd: float


PLANS: dict[str, Plan] = {
    "free": Plan("free", 0.50, allow_deep=False, monthly_price_usd=0.0),
    "pro": Plan("pro", 5.00, allow_deep=True, monthly_price_usd=19.0),
    "enterprise": Plan("enterprise", 100.0, allow_deep=True, monthly_price_usd=199.0),
}


def get_plan(name: str | None) -> Plan:
    return PLANS.get(name or "free", PLANS["free"])


@dataclass
class QuotaDecision:
    allowed: bool
    action: str  # allow | downgrade | block
    reason: str
    remaining_usd: float


def decide_quota(plan: Plan, spent_today_usd: float, *, wants_deep: bool = False) -> QuotaDecision:
    """현재 일일 소비 + 요청 특성으로 허용/강등/차단 결정."""
    remaining = round(plan.daily_cost_limit_usd - spent_today_usd, 6)
    if remaining <= 0:
        return QuotaDecision(False, "block", "일일 비용 한도를 초과했습니다.", remaining)
    if wants_deep and not plan.allow_deep:
        return QuotaDecision(True, "downgrade", "현재 요금제는 심층 분석을 제공하지 않습니다(표준으로 진행).", remaining)
    if wants_deep and remaining < 0.2 * plan.daily_cost_limit_usd:
        return QuotaDecision(True, "downgrade", "잔여 한도가 적어 표준 분석으로 진행합니다.", remaining)
    return QuotaDecision(True, "allow", "ok", remaining)
