"""모닝리포트 데이터 컨테이너."""
from __future__ import annotations

from dataclasses import dataclass, field

from models.market import MarketSummary
from models.news import NewsArticle


@dataclass
class MorningReportData:
    date: str  # YYYY-MM-DD
    generated_at: str = ""  # 생성 시각 표시용
    summary: MarketSummary = field(default_factory=MarketSummary)
    top_news: list[NewsArticle] = field(default_factory=list)
    calendar: list = field(default_factory=list)  # EconomicEvent[]
    notes: list[str] = field(default_factory=list)  # 데이터 수집 경고 등
