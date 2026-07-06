"""모닝리포트 생성 → docs/morning/YYYY-MM-DD/index.html + 아카이브 + cache/news.json.

데이터는 pipelines(계층 경유)로만 받는다. 검증 안 된 값은 행 자체를 생략(팩트 우선).
"""
from __future__ import annotations

from pathlib import Path

from calculators import news_rank, themes as themes_calc
from config.settings import CACHE_DIR, DOCS_DIR
from generators import pipelines
from generators.base import render
from models.report import MorningReportData
from utils import runlog
from utils.dates import fmt_kst, now_kst, today_str
from utils.jsonio import save_json
from utils.logging import get_logger

log = get_logger("gen.morning")

_WD_KR = "월화수목금토일"
_KR_KEYS = ("kospi_night", "kosdaq_night", "usdkrw", "wti")
_US_KEYS = ("nasdaq", "sp500", "dow", "sox")


def _build_data() -> MorningReportData:
    market = pipelines.get_market()
    news = pipelines.get_news()
    top7 = news_rank.top(news, 7)
    theme_list = runlog.run_step(
        "Theme Analyst", lambda: themes_calc.extract_themes(news, top_n=3), fallback=[]
    ) or []

    save_json(
        CACHE_DIR / "news.json",  # 리포트 산출물(기사 저장소 news_articles.json과 분리)
        {
            "generated_at": now_kst().isoformat(),
            "top7": [a.to_dict() for a in top7],
            "themes": theme_list,
        },
    )

    kr_rows = [market[k] for k in _KR_KEYS if market.get(k)]
    us_rows = [market[k] for k in _US_KEYS if market.get(k)]

    notes: list[str] = []
    if market.get("kospi_night") is None and market.get("kosdaq_night") is None:
        notes.append("야간선물 데이터 없음 — 데스크톱 Kiwoom 동기화 시 표시됩니다.")
    else:
        notes.append("야간선물 등락률은 전일 정규장 종가 대비입니다(당일 주간 변동 포함).")
    if not us_rows:
        notes.append("미국시장 데이터를 불러오지 못했습니다(소스 지연/오프라인).")
    if not top7:
        notes.append("뉴스 수집 결과가 없습니다.")

    now = now_kst()
    return MorningReportData(
        date=today_str(),
        date_display=f"{now:%Y.%m.%d} ({_WD_KR[now.weekday()]})",
        generated_at=fmt_kst(now) + " KST",
        kr_rows=kr_rows,
        us_rows=us_rows,
        top_news=top7,
        themes=theme_list,
        notes=notes,
    )


def list_dates() -> list[str]:
    """발행된 모닝리포트 날짜(YYYY-MM-DD) 최신순 — 아카이브/대시보드 공용."""
    base = DOCS_DIR / "morning"
    if not base.exists():
        return []
    return sorted((p.name for p in base.iterdir() if p.is_dir() and p.name[:1].isdigit()), reverse=True)


def generate() -> Path:
    data = _build_data()
    out = DOCS_DIR / "morning" / data.date / "index.html"
    render("morning.html", {"active": "morning", "root": "../..", "data": data}, out)
    _archive()
    log.info("모닝리포트 생성: %s", out)
    return out


def _archive() -> None:
    render(
        "morning_index.html",
        {"active": "morning", "root": "..", "dates": list_dates()},
        DOCS_DIR / "morning" / "index.html",
    )
