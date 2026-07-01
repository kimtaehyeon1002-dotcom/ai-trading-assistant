"""모닝리포트 데이터 조립 — 시장요약 + 핵심뉴스 + 경제캘린더."""
from __future__ import annotations

from core.dates import fmt_kst, now_kst, today_str
from models.report import MorningReportData
from services.market.calendar import get_economic_calendar
from services.market.summary import build_summary
from services.news import collector, store


def _top_news(news, n: int = 8):
    """속보/매크로/반도체를 우선 가중, 그 외 최신순."""
    def weight(a):
        w = 0
        if "breaking" in a.categories:
            w += 3
        if "macro" in a.categories:
            w += 1
        if "semiconductor" in a.categories or "ai" in a.categories:
            w += 1
        return w

    ranked = sorted(news, key=lambda a: (weight(a), a.published or now_kst()), reverse=True)
    return ranked[:n]


def build_morning() -> MorningReportData:
    summary = build_summary()
    news = store.merge_and_save(collector.collect())
    calendar = get_economic_calendar()

    notes: list[str] = []
    if summary.indices and all(i.price is None for i in summary.indices):
        notes.append("시세 데이터를 불러오지 못했습니다(오프라인/소스 지연). 일부 표가 비어 있을 수 있습니다.")
    if not news:
        notes.append("뉴스 수집 결과가 없습니다.")

    return MorningReportData(
        date=today_str(),
        generated_at=fmt_kst(now_kst()) + " KST",
        summary=summary,
        top_news=_top_news(news, 8),
        calendar=calendar,
        notes=notes,
    )
