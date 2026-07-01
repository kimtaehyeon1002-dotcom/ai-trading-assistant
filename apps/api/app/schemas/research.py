"""AI Research 스키마 — 요청/의도분류/4-블록 결과/잡 봉투. 설계서 §2.4, §7.2.

핵심 제약(법적): 매수/매도 권유·목표주가·매매 시그널 금지. 모든 출력은
4-블록(①사실/데이터 ②관찰 포인트 ③시나리오와 전제 ④리스크/면책) + 면책으로만 구성.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    instrument_id: int | None = None
    symbol: str | None = None  # market+symbol 해소용(검색)
    market: str | None = None
    query: str | None = None  # 자유 질문("이 종목 어때?", "이거 사도 돼?")
    style: str = "swing"  # scalping | swing | long
    depth: str = "standard"  # standard(Sonnet) | deep(Opus)
    language: str = "ko"


class IntentClassification(BaseModel):
    intent: str = "research"  # research | trade_decision | concept | other
    instruments: list[str] = Field(default_factory=list)  # 추출된 종목 표기
    is_trade_decision: bool = False  # "사도 돼?" 류 매매결정 요구 감지
    timeframe: str | None = None  # intraday | swing | long
    language: str = "ko"
    note: str | None = None


class ResearchBlocks(BaseModel):
    facts: list[str] = Field(default_factory=list)  # ① 사실/데이터
    observations: list[str] = Field(default_factory=list)  # ② 관찰 포인트/체크리스트
    scenarios: list[str] = Field(default_factory=list)  # ③ 시나리오와 전제(복수·균형)
    risks: list[str] = Field(default_factory=list)  # ④ 리스크/면책


class Citation(BaseModel):
    n: int
    title: str
    url: str | None = None
    source: str | None = None
    published_at: datetime | None = None


class ResearchResult(BaseModel):
    job_id: str
    status: str  # completed | blocked | error
    blocked: bool = False
    instrument_id: int | None = None
    symbol_norm: str | None = None
    title: str
    markdown: str  # 가드레일 통과 + 면책 포함 최종 본문
    blocks: ResearchBlocks | None = None
    citations: list[Citation] = Field(default_factory=list)
    disclaimer_version: str
    intent: IntentClassification | None = None
    model: str | None = None
    cost_usd: float = 0.0
    created_at: datetime | None = None


class JobEnvelope(BaseModel):
    """POST /research/jobs 202 응답 — 설계서 §7.1 Job 패턴."""

    job_id: str
    status: str  # pending | running | completed | blocked | error
    stream_url: str
    result_url: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    error: str | None = None
    result_url: str | None = None


class NoteIn(BaseModel):
    """개인 노트(개인 RAG, 본인만 검색됨). 설계서 §5.3 RLS."""

    title: str | None = None
    text: str
    symbols: list[str] = Field(default_factory=list)
    market: str | None = None
