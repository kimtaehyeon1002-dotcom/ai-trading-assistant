"""모닝리포트 데이터 컨테이너 — 한국시장/미국시장/TOP7 뉴스/주목 테마(고정 섹션)."""
from __future__ import annotations

from dataclasses import dataclass, field

from models.news import NewsArticle


@dataclass
class MorningReportData:
    date: str  # YYYY-MM-DD
    date_display: str = ""  # YYYY.MM.DD (요일)
    generated_at: str = ""
    kr_rows: list = field(default_factory=list)  # Quote[] — 야간선물/환율/WTI (검증된 값만)
    us_rows: list = field(default_factory=list)  # Quote[] — NASDAQ/S&P500/DOW/SOX
    top_news: list[NewsArticle] = field(default_factory=list)  # TOP 7
    themes: list = field(default_factory=list)  # [{name, count, sample}]
    notes: list[str] = field(default_factory=list)  # 데이터 수집 경고(투명성)
