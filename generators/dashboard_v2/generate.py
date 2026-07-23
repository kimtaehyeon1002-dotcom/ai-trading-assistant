"""Dashboard v2 생성 → docs/index.html (v2 셸, 5카드: Hero/한국지수/미국지수/핵심뉴스/오늘일정).

design/01. 자산(Notion ERP) 콘텐츠는 이 페이지에 존재하지 않는다 — design/20 Phase 4 DoD
"자산 절대값·역산 가능값 grep 0건"을 코드 구조로 보장한다(애초에 관련 데이터를 취득하지 않음).

v1 생성기(generators/dashboard/generate.py)·템플릿(templates/dashboard.html)은 롤백 대상으로
그대로 보존한다 — 되돌리려면 build.py의 import 한 줄만 v1으로 바꾸면 된다(design/20 Phase 4
리스크·롤백: "생성기 파일 교체 단위").
"""
from __future__ import annotations

from pathlib import Path

from calculators import news_categories, news_rank
from config import nav
from config.calendar import KR_NIGHT_CLOSE, KR_NIGHT_OPEN, SESSIONS
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from generators.morning.generate import list_dates
from models.market import Quote
from utils.dates import fmt_kst, now_kst

# 주간지수 → 야간선물 → 환율 순(2열 그리드에서 행 단위로 짝이 맞는다).
# kosdaq_night 누락은 design/23 P3 — 수집·저장은 정상인데 표시면에만 키가 없어
# "코스닥 야간선물이 어디에도 안 보이던" 결함이었다(모닝 dated 페이지 은퇴 후
# 대시보드가 유일한 표시면이므로 여기 없으면 사이트 전체에 없다).
_KR_TILE_KEYS = ("kospi", "kosdaq", "kospi_night", "kosdaq_night", "usdkrw")
_US_TILE_KEYS = ("sp500", "nasdaq", "dow", "vix")


def _headline(market: dict[str, Quote | None]) -> str | None:
    """사실 조립형 한 줄 요약 — 해석·인과 분석 없이 방향성 사실만 나열(no-AI 원칙).

    데이터 결측 시 문장 행 자체를 생략한다(design/20 Phase 4 DoD 3 — 팩트 우선, 빈 문장 금지).
    """
    parts: list[str] = []
    us_quotes = [market.get(k) for k in ("sp500", "nasdaq", "dow") if market.get(k)]
    if us_quotes:
        ups = sum(1 for q in us_quotes if q.up)
        if ups == len(us_quotes):
            parts.append("미국 3대 지수 상승 마감")
        elif ups == 0:
            parts.append("미국 3대 지수 하락 마감")
        else:
            parts.append("미국 3대 지수 혼조 마감")
    kospi = market.get("kospi")
    if kospi and kospi.change_pct is not None:
        sign = "▲" if kospi.up else "▼"
        parts.append(f"코스피 {sign} {abs(kospi.change_pct):.2f}%")
    return " · ".join(parts) if parts else None


def _schedule_rows() -> list[dict]:
    """세션 룰(config/calendar) 기반 오늘 일정 — Notion 일정 DB 연동 전까지의 사실 기반 최소 구현.

    design/21 §2-1: "세션 룰(config) + Notion 일정 DB, 현행 세션 룰만" — Notion 미설정(이 환경
    포함) 상태에서도 항상 사실에 근거한 행만 표시한다(추정·가짜 일정 금지).
    """
    kr = SESSIONS["kr"]
    rows = [
        {"time": kr.regular_open, "label": "국내 증시 개장"},
        {"time": kr.regular_close, "label": "국내 증시 마감"},
        {"time": KR_NIGHT_OPEN, "label": "야간선물 세션 개시"},
        {"time": KR_NIGHT_CLOSE, "label": "야간선물 세션 마감"},
    ]
    if kr.pre_open:
        rows.insert(0, {"time": kr.pre_open, "label": "국내 증시 장전"})
    return sorted(rows, key=lambda r: r["time"])


def _build_context() -> dict:
    market = pipelines.get_market()
    news = pipelines.get_news()
    top5 = news_rank.top(news, 5)
    recent = sorted(news, key=lambda a: a.published or now_kst(), reverse=True)[:8]
    dates = list_dates()

    return {
        "root": ".",
        "nav": nav.context(active="dashboard"),
        "generated_at": fmt_kst(now_kst()) + " KST",
        "headline": _headline(market),
        "market": market,
        "kr_tiles": [(k, market.get(k)) for k in _KR_TILE_KEYS],
        "us_tiles": [(k, market.get(k)) for k in _US_TILE_KEYS],
        "top_news": top5,
        "recent_news": [(a, news_categories.primary_label(a)) for a in recent],
        "schedule": _schedule_rows(),
        "latest_morning": dates[0] if dates else None,
    }


def generate() -> Path:
    return render("pages/dashboard_v2.html", _build_context(), DOCS_DIR / "index.html")
