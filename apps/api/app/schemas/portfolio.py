"""포트폴리오 스키마 — 보유 입력/조회 + 코드 메트릭 + 분석 결과. 설계서 §2.4, §7.2.

분석은 분산 개념·관찰 포인트 중심(리밸런싱 '지시' 금지) + 면책.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HoldingIn(BaseModel):
    instrument_id: int | None = None
    symbol: str | None = None  # instrument 해소용(둘 중 하나)
    quantity: float
    avg_cost: float | None = None


class HoldingOut(BaseModel):
    holding_id: str
    instrument_id: int
    symbol_norm: str | None = None
    name: str | None = None
    market: str | None = None
    currency: str | None = None
    quantity: float
    avg_cost: float | None = None
    price: float | None = None  # 현재가(종목 통화)
    value_base: float | None = None  # 평가액(기준통화 환산)
    weight: float | None = None
    valuation_basis: str = "market"  # market | cost | none


class ExposureBucket(BaseModel):
    value: float = 0.0
    weight: float = 0.0


class PortfolioMetrics(BaseModel):
    base_currency: str = "KRW"
    total_value: float = 0.0
    n_positions: int = 0
    hhi: float = 0.0
    effective_n: float = 0.0
    concentration_band: str = "낮음"  # 낮음 | 보통 | 높음 (관찰 지표)
    top1_weight: float = 0.0
    top3_weight: float = 0.0
    top5_weight: float = 0.0
    positions: list[dict] = Field(default_factory=list)
    by_sector: dict[str, ExposureBucket] = Field(default_factory=dict)
    by_market: dict[str, ExposureBucket] = Field(default_factory=dict)
    by_currency: dict[str, ExposureBucket] = Field(default_factory=dict)
    valuation_note: str | None = None  # 일부 종목 시세 미수집 등


class PortfolioBlocks(BaseModel):
    composition: list[str] = Field(default_factory=list)  # ① 구성·노출 사실
    observations: list[str] = Field(default_factory=list)  # ② 집중·편중 관찰
    scenarios: list[str] = Field(default_factory=list)  # ③ 분산 관점 시나리오·전제
    risks: list[str] = Field(default_factory=list)  # ④ 리스크/면책


class PortfolioAnalysisResult(BaseModel):
    status: str  # completed | blocked
    blocked: bool = False
    title: str
    markdown: str
    blocks: PortfolioBlocks | None = None
    metrics: PortfolioMetrics
    disclaimer_version: str
    model: str | None = None
    cost_usd: float = 0.0
