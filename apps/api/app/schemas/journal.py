"""매매일지 스키마 — Notion 정규화 거래 + 코드 메트릭 + 코치 결과. 설계서 §1.3-C, §2.4.

핵심 제약: 코치는 개별 종목 권유·목표가 없이 행동 패턴+일반 리스크관리 교육만. 면책 필수.
Notion '매매 일지 _ 쉽알남' 스키마: 날짜/종목명/포지션(Long·Short)/수익금(USD)/승·무·패/매매 복기.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class JournalTrade(BaseModel):
    """Notion 행 → 정규화 거래(완결 거래 1건 = 1행)."""

    row_id: str  # Notion page id (멱등 키)
    traded_on: date | None = None
    symbol: str | None = None  # BTC|ETH|SOL|XRP ...
    position: str | None = None  # long | short
    pnl: float | None = None  # 수익금(USD), 음수=손실
    outcome: str = "unknown"  # win | loss | draw | unknown
    note: str | None = None  # 매매 복기(사용자 본인 기록)


class ImportResult(BaseModel):
    source: str = "notion"
    imported: int = 0
    skipped: int = 0
    total_seen: int = 0
    source_unavailable: bool = False
    is_stub: bool = False


class JournalEntryOut(BaseModel):
    entry_id: str
    traded_on: date | None = None
    symbol: str | None = None
    position: str | None = None
    pnl: float | None = None
    outcome: str
    note: str | None = None


class BucketStat(BaseModel):
    n: int = 0
    net_pnl: float = 0.0
    win_rate: float | None = None


class JournalMetrics(BaseModel):
    n_trades: int = 0
    n_wins: int = 0
    n_losses: int = 0
    n_draws: int = 0
    win_rate: float | None = None  # wins / (wins+losses)
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0  # 음수
    avg_win: float | None = None
    avg_loss: float | None = None  # 음수
    avg_trade: float | None = None
    profit_factor: float | None = None  # gross_profit / |gross_loss|
    payoff_ratio: float | None = None  # avg_win / |avg_loss|
    expectancy: float | None = None  # 기대값(거래당)
    max_win_streak: int = 0
    max_loss_streak: int = 0
    max_drawdown: float = 0.0  # 누적손익 곡선 최대 낙폭(절대값, USD)
    by_symbol: dict[str, BucketStat] = Field(default_factory=dict)
    by_position: dict[str, BucketStat] = Field(default_factory=dict)
    by_weekday: dict[str, BucketStat] = Field(default_factory=dict)
    # 데이터가 없어 계산 불가한 지표(정직하게 표기)
    unavailable: list[str] = Field(default_factory=list)


class CoachBlocks(BaseModel):
    performance: list[str] = Field(default_factory=list)  # ① 성과 요약(사실/지표)
    patterns: list[str] = Field(default_factory=list)  # ② 행동 패턴/편향 관찰
    checklist: list[str] = Field(default_factory=list)  # ③ 리스크관리 체크리스트(교육)
    risks: list[str] = Field(default_factory=list)  # ④ 리스크/면책


class CoachRequest(BaseModel):
    question: str | None = None


class CoachResult(BaseModel):
    status: str  # completed | blocked
    blocked: bool = False
    title: str
    markdown: str
    blocks: CoachBlocks | None = None
    metrics: JournalMetrics
    is_trade_decision: bool = False  # "지금 다시 살까?" 류 감지 → 교육+면책 라우팅
    disclaimer_version: str
    model: str | None = None
    cost_usd: float = 0.0
