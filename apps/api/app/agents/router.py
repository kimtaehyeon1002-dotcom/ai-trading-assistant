"""작업 유형 → Claude 모델 라우팅 정책. (설계서 §2.2)

분류/추출/라우팅/가드레일 판별 = Haiku, 일반/대량 분석 = Sonnet, 심층/합성 = Opus.
"""
from __future__ import annotations

from enum import Enum

OPUS = "claude-opus-4-8"
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5"

# 모델별 단가 (USD per 1M tokens): (input, output)
PRICING: dict[str, tuple[float, float]] = {
    OPUS: (5.0, 25.0),
    SONNET: (3.0, 15.0),
    HAIKU: (1.0, 5.0),
}


class Task(str, Enum):
    PING = "ping"
    CLASSIFY = "classify"
    ROUTE = "route"
    COMPLIANCE_CHECK = "compliance_check"
    RESEARCH = "research"
    RESEARCH_DEEP = "research_deep"
    MORNING_REPORT = "morning_report"
    JOURNAL_ANALYSIS = "journal_analysis"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"


_TASK_MODEL: dict[Task, str] = {
    Task.PING: HAIKU,
    Task.CLASSIFY: HAIKU,
    Task.ROUTE: HAIKU,
    Task.COMPLIANCE_CHECK: HAIKU,
    Task.RESEARCH: SONNET,
    Task.RESEARCH_DEEP: OPUS,
    Task.MORNING_REPORT: OPUS,
    Task.JOURNAL_ANALYSIS: SONNET,
    Task.PORTFOLIO_ANALYSIS: SONNET,
}


def model_for(task: Task | str) -> str:
    if isinstance(task, str):
        task = Task(task)
    return _TASK_MODEL.get(task, SONNET)
