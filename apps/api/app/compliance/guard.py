"""가드레일 오케스트레이션 — 규칙 1차 필터 → (Phase 2: 2차 LLM) → 면책 주입.

fail-closed: 검증기 오류 시 통과가 아니라 차단. 모든 사용자 노출 LLM 출력이 통과해야 한다.
설계서 §0, §2.6.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.compliance.disclaimers import attach_disclaimer
from app.compliance.rules import RuleHit, scan

NEUTRAL_BLOCK_MESSAGE = (
    "요청하신 내용은 매수/매도 권유나 목표가 등 투자판단 자문에 해당할 수 있어 제공할 수 없습니다. "
    "대신 관련 사실·관찰 포인트·시나리오·리스크를 중립적으로 안내드릴 수 있습니다."
)


@dataclass
class GuardResult:
    ok: bool  # 위반 없음
    blocked: bool  # 차단됨
    text: str  # 사용자에게 나갈 최종 텍스트(면책 포함)
    flags: list[RuleHit] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


def guard_output(text: str, *, block_on_violation: bool = True) -> GuardResult:
    """1차 규칙 검증 + 면책. Phase 2에서 2차 LLM 분류기/재작성 루프를 끼운다."""
    try:
        hits = scan(text)
    except Exception:  # noqa: BLE001 - fail-closed
        return GuardResult(
            ok=False, blocked=True, text=attach_disclaimer(NEUTRAL_BLOCK_MESSAGE)
        )

    if hits and block_on_violation:
        return GuardResult(
            ok=False,
            blocked=True,
            text=attach_disclaimer(NEUTRAL_BLOCK_MESSAGE),
            flags=hits,
            categories=sorted({h.category for h in hits}),
        )

    return GuardResult(
        ok=not hits,
        blocked=False,
        text=attach_disclaimer(text),
        flags=hits,
        categories=sorted({h.category for h in hits}),
    )


async def guard_research_output(
    text: str,
    *,
    session=None,
    user_id: uuid.UUID | None = None,
    block_on_violation: bool = True,
) -> GuardResult:
    """단일 통과 지점(2계층): 규칙 1차(fail-closed) → 가능 시 2차 LLM 분류기 → 면책.

    규칙에서 이미 차단되면 즉시 반환. 통과 시 Haiku 분류기로 의미 기반 우회를 보강한다
    (ANTHROPIC_API_KEY 없으면 분류기는 비활성, 규칙 결과만).
    """
    base = guard_output(text, block_on_violation=block_on_violation)
    if base.blocked:
        return base

    try:
        from app.compliance.classifier import classify_violation

        verdict = await classify_violation(text, session=session, user_id=user_id)
    except Exception:  # noqa: BLE001 - 분류기 보강 실패는 규칙 결과를 무효화하지 않음
        verdict = None

    if verdict is not None and verdict.violation and block_on_violation:
        cats = list(base.categories)
        if verdict.category and verdict.category not in cats:
            cats.append(verdict.category)
        return GuardResult(
            ok=False,
            blocked=True,
            text=attach_disclaimer(NEUTRAL_BLOCK_MESSAGE),
            flags=base.flags,
            categories=sorted(cats),
        )
    return base
