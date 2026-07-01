"""2차 LLM 분류기 — 규칙이 못 잡는 의미 기반 우회 탐지(Haiku). 설계서 §2.6 B-2.

규칙 1차 필터(rules.scan)가 항상 유효한 1차 방어선이며, 본 분류기는 보강이다.
ANTHROPIC_API_KEY 없으면 비활성(checked=False) — 규칙 결과만 사용.
분류기 호출 자체가 실패하면 violation으로 단정하지 않되(규칙은 이미 통과), 경고 로깅.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude import get_claude, persist_agent_run
from app.agents.router import Task
from app.core.logging import get_logger

log = get_logger("classifier")

CLASSIFIER_SYSTEM = """\
너는 한국 자본시장법 컴플라이언스 분류기다. 입력 텍스트가 '투자 권유/매매지시/목표가/수익보장/\
1:1 종목지정'에 해당하는지 판별한다. 반드시 아래 JSON 객체 하나만 출력한다.
{"violation": true, "category": "buy_sell|target_price|return_promise|guarantee|impersonation|none", "span": "위반 근거 구절 또는 빈 문자열"}
교육/개념 설명("손절매란")과 균형 잡힌 정보 제공은 violation=false 로 둔다."""


@dataclass
class ClassifierVerdict:
    violation: bool
    category: str | None = None
    span: str | None = None
    checked: bool = False  # LLM이 실제 검사했는지(스텁/비활성/오류=False)


async def classify_violation(
    text: str, *, session: AsyncSession | None = None, user_id: uuid.UUID | None = None
) -> ClassifierVerdict:
    claude = get_claude()
    if not claude.enabled:
        return ClassifierVerdict(violation=False, checked=False)
    try:
        result = await claude.complete(
            Task.COMPLIANCE_CHECK,
            system=CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": text[:4000]}],
            max_tokens=200,
        )
        if session is not None:
            await persist_agent_run(session, result, user_id=user_id)
        if result.is_stub:
            return ClassifierVerdict(violation=False, checked=False)
        m = re.search(r"\{.*\}", result.text, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        cat = data.get("category")
        return ClassifierVerdict(
            violation=bool(data.get("violation")),
            category=cat if cat and cat != "none" else None,
            span=data.get("span") or None,
            checked=True,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("classifier_failed", error=str(exc))
        return ClassifierVerdict(violation=False, checked=False)
