"""RAG 평가 — 근거성(faithfulness) LLM-judge + 검색 품질 지표(Recall@k·MRR). 설계서 §5.2.

품질 지표(recall_at_k·mrr)는 순수 함수(stdlib) → 골든셋 회귀에 사용, 오프라인 테스트 가능.
faithfulness는 Haiku 판별(키 없으면 미검사). '근거없음' 임계 초과 시 상위에서 차단/재생성 가능.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """상위 k 검색 결과의 관련 문서 재현율."""
    if not relevant:
        return 0.0
    topk = retrieved[:k]
    hit = len(set(topk) & relevant)
    return hit / len(relevant)


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    """첫 관련 문서의 역순위(Mean Reciprocal Rank의 단일 쿼리 값)."""
    for i, r in enumerate(retrieved, 1):
        if r in relevant:
            return 1.0 / i
    return 0.0


_FAITHFUL_SYSTEM = """\
너는 RAG 답변의 근거성(faithfulness) 평가자다. 답변이 제공된 컨텍스트로 뒷받침되는지 판별한다.
반드시 아래 JSON 하나만 출력한다.
{"faithful": true, "score": 0.0, "unsupported": ["근거 없는 주장"]}
score는 0~1(근거성). 컨텍스트에 없는 사실 주장이 있으면 faithful=false."""


async def evaluate_faithfulness(
    answer: str,
    contexts: list[str],
    *,
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> dict:
    """Haiku 근거성 판별. 키 없으면 {checked: False}. 상위에서 임계 비교에 사용."""
    from app.agents.claude import get_claude, persist_agent_run
    from app.agents.router import Task
    from app.core.logging import get_logger

    log = get_logger("rag_eval")
    claude = get_claude()
    if not claude.enabled:
        return {"faithful": True, "score": None, "unsupported": [], "checked": False}
    ctx = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))[:8000]
    try:
        result = await claude.complete(
            Task.CLASSIFY,
            system=_FAITHFUL_SYSTEM,
            messages=[{"role": "user", "content": f"[답변]\n{answer[:4000]}\n\n[컨텍스트]\n{ctx}"}],
            max_tokens=300,
        )
        if session is not None:
            await persist_agent_run(session, result, user_id=user_id)
        if result.is_stub:
            return {"faithful": True, "score": None, "unsupported": [], "checked": False}
        m = re.search(r"\{.*\}", result.text, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        return {
            "faithful": bool(data.get("faithful", True)),
            "score": data.get("score"),
            "unsupported": data.get("unsupported") or [],
            "checked": True,
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("faithfulness_failed", error=str(exc))
        return {"faithful": True, "score": None, "unsupported": [], "checked": False}
