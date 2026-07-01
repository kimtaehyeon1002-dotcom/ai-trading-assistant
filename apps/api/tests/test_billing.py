"""Phase 7 — 요금제/쿼터 결정(순수). 오프라인 실행 가능.

usage_service는 sqlalchemy 의존 → Docker. plans는 stdlib만.
"""
from __future__ import annotations

from app.billing.plans import PLANS, decide_quota, get_plan


def test_plan_registry():
    assert get_plan("free").daily_cost_limit_usd == 0.50
    assert get_plan("pro").allow_deep is True
    assert get_plan(None).name == "free"  # 미상 → free
    assert get_plan("nope").name == "free"
    for p in PLANS.values():
        assert p.daily_cost_limit_usd > 0


def test_block_when_over_limit():
    d = decide_quota(get_plan("free"), spent_today_usd=0.60)
    assert d.allowed is False and d.action == "block"
    assert d.remaining_usd < 0


def test_allow_under_limit():
    d = decide_quota(get_plan("pro"), spent_today_usd=1.0)
    assert d.allowed is True and d.action == "allow"
    assert d.remaining_usd == 4.0


def test_downgrade_deep_on_free_plan():
    # free는 심층(Opus) 비허용 → 강등(차단은 아님)
    d = decide_quota(get_plan("free"), spent_today_usd=0.0, wants_deep=True)
    assert d.allowed is True and d.action == "downgrade"


def test_downgrade_deep_when_low_remaining():
    # pro인데 잔여 한도 < 20% → 심층 요청은 강등
    d = decide_quota(get_plan("pro"), spent_today_usd=4.5, wants_deep=True)
    assert d.action == "downgrade"


def test_allow_deep_with_budget():
    d = decide_quota(get_plan("pro"), spent_today_usd=0.0, wants_deep=True)
    assert d.action == "allow"
