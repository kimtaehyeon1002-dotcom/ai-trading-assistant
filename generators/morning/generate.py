"""모닝리포트 데이터 파이프라인 → cache/news.json(신규 dated 페이지 발행은 영구 중단, 아래 주석).

데이터는 pipelines(계층 경유)로만 받는다. 검증 안 된 값은 행 자체를 생략(팩트 우선).
"""
from __future__ import annotations

from pathlib import Path

from calculators import news_rank, themes as themes_calc
from config.settings import CACHE_DIR
from generators import pipelines
from models.report import MorningReportData
from repositories import market_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst, today_str
from utils.jsonio import save_json
from utils.logging import get_logger

log = get_logger("gen.morning")

# design/20 Phase 5 정리점 결정, Phase 9에서 영구화(design/20 Phase 9 "이중 유지보수 종료"):
# Dashboard(Phase 4)·News(Phase 5)가 모닝 콘텐츠(지수·핵심뉴스·오늘 일정)를 전부 커버해 신규
# dated 페이지 발행을 영구 중단한다. 데이터 파이프라인(_build_data — get_market·get_news·
# Theme Analyst runlog 계측)은 계속 실행한다(캐시 소비처 유지). 이 모듈은 이제 페이지를
# 전혀 쓰지 않는 순수 데이터 스텝이다.
#
# design/25(2026-07-29): 동결 보존하던 아카이브(docs/morning/YYYY-MM-DD/)를 **삭제**했다.
# v1 셸 상속 페이지라 v1 CSS/JS 은퇴 후 스타일이 깨졌고 nav도 구 5링크를 가리켜 죽은 링크였다.
# 내용은 Dashboard·News가 전부 커버하므로 손실이 없다. 복원은 git 히스토리에서 한다.
# 이에 따라 list_dates()와 대시보드의 "리포트 전문 보기" 버튼도 함께 제거했다.

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
    night_note = market_repository.night_basis_note(market)
    if night_note is None:
        notes.append("야간선물 데이터 없음 — 데스크톱 Kiwoom 동기화 시 표시됩니다.")
    else:
        notes.append(night_note)
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


def generate() -> Path | None:
    """데이터 파이프라인만 실행하고 페이지는 쓰지 않는다(신규 발행 영구 중단, 위 주석 참조)."""
    _build_data()
    log.info("모닝리포트 신규 발행 중단(정리점 결정, 영구) — 데이터 파이프라인만 실행됨")
    return None
