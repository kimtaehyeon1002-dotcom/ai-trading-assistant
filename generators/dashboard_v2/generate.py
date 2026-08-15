"""Morning Report 생성 → docs/morning/index.html (v2 셸, 5카드: Hero/한국지수/미국지수/핵심뉴스/오늘일정).

첫 화면(docs/index.html)은 이동 전용 런처로 분리했다(generators/launcher).

design/01. 자산(ERP) 콘텐츠는 이 페이지에 존재하지 않는다 — design/20 Phase 4 DoD
"자산 절대값·역산 가능값 grep 0건"을 코드 구조로 보장한다(애초에 관련 데이터를 취득하지 않음).

v1 생성기(generators/dashboard/)·템플릿(templates/dashboard.html)은 Phase 9 v1 셸 은퇴로
소스에서 제거됐다 — 롤백이 필요하면 git 히스토리에서 복원한다.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from calculators import news_categories, news_rank
from config import nav
from config import calendar as cal
from config.calendar import KR_NIGHT_CLOSE, KR_NIGHT_OPEN, SESSIONS
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from models.market import Quote
from repositories import market_repository
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


def _schedule_rows(today: date) -> list[dict]:
    """세션 룰(config/calendar) 기반 오늘 일정 — 외부 일정 소스 연동 전까지의 사실 기반 최소 구현.

    design/21 §2-1이 상정한 외부 일정 DB는 연동돼 있지 않다(Notion 연동은 vault 이관으로 폐기).
    소스가 없는 상태에서도 항상 사실에 근거한 행만 표시한다(추정·가짜 일정 금지).

    **요일·공휴일을 반영한다.** 이전 구현은 날짜와 무관하게 5행을 그대로 찍어서, 토요일에도
    "09:00 국내 증시 개장"이 떴다(실측 2026-08-15 토요일·광복절). 일정 카드가 열리지 않는
    장을 열린다고 말하는 것은 이 페이지에서 가장 직접적인 거짓말이다.

    야간선물 마감(05:00)은 **전일 세션의 끝**이라 오늘이 휴장이어도 어제가 영업일이면 사실이다
    (금요일 18:00 개시 → 토요일 05:00 마감). 그래서 개시/마감을 각각 다른 날짜로 판정한다.
    """
    kr = SESSIONS["kr"]
    rows: list[dict] = []

    # 어제 열렸다면 그 야간 세션은 오늘 새벽에 끝난다 — 오늘이 주말이어도 실제로 일어난 일이다.
    if cal.is_trading_day(kr, today - timedelta(days=1)):
        rows.append({"time": KR_NIGHT_CLOSE, "label": "야간선물 세션 마감", "note": "전일 세션"})

    if cal.is_trading_day(kr, today):
        if kr.pre_open:
            rows.append({"time": kr.pre_open, "label": "국내 증시 장전"})
        rows.append({"time": kr.regular_open, "label": "국내 증시 개장"})
        rows.append({"time": kr.regular_close, "label": "국내 증시 마감"})
        rows.append({"time": KR_NIGHT_OPEN, "label": "야간선물 세션 개시"})

    return sorted(rows, key=lambda r: r["time"])


def _schedule_meta(today: date) -> dict:
    """휴장 사유와 다음 영업일 — 일정이 비었을 때 "왜 비었는가"를 말해 주는 재료.

    공휴일 목록이 음력 명절·대체공휴일까지 담고 있지 않으므로(config/calendar 주석 참조)
    "영업일로 보인다"는 판정은 단정하지 않는다. 확실한 것(주말·등재 공휴일)만 사유로 밝힌다.
    """
    kr = SESSIONS["kr"]
    reason = cal.holiday_label(kr, today)
    nxt = cal.next_trading_day(kr, today) if reason else None
    return {
        "closed": reason is not None,
        "reason": reason,
        "next_open": nxt.strftime("%m/%d(%a)").replace("Mon", "월").replace("Tue", "화")
        .replace("Wed", "수").replace("Thu", "목").replace("Fri", "금") if nxt else None,
    }


def _build_context() -> dict:
    market = pipelines.get_market()
    news = pipelines.get_news()
    top5 = news_rank.top(news, 5)
    recent = sorted(news, key=lambda a: a.published or now_kst(), reverse=True)[:8]

    return {
        "root": "..",
        "nav": nav.context(active="morning"),
        "generated_at": fmt_kst(now_kst()) + " KST",
        "headline": _headline(market),
        "market": market,
        "kr_tiles": [(k, market.get(k)) for k in _KR_TILE_KEYS],
        # 야간선물 등락 기준 고지(design/27). 모닝 dated 페이지 은퇴 후 대시보드가 유일한
        # 표시면이므로, 여기 없으면 "이 %가 무엇 대비인가"를 사이트 어디서도 알 수 없다.
        "kr_basis_note": market_repository.night_basis_note(market),
        "us_tiles": [(k, market.get(k)) for k in _US_TILE_KEYS],
        "top_news": top5,
        "recent_news": [(a, news_categories.primary_label(a)) for a in recent],
        "schedule": _schedule_rows(now_kst().date()),
        "schedule_meta": _schedule_meta(now_kst().date()),
    }


def generate() -> Path:
    return render("pages/dashboard_v2.html", _build_context(), DOCS_DIR / "morning" / "index.html")
