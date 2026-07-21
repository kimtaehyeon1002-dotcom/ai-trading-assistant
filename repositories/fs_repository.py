"""종목 재무 5개 지표 카드 조립 + docs/data/financials/<code>.json 기록(design/06, Phase 7).

집계·판정 로직은 calculators/fs_indicators가 순수 함수로 담당한다 — 이 리포지토리는 컨테이너
조립·영속화만 한다. financials가 None(수집 실패·키 미설정)이어도 5개 카드 전부 None으로 채워
정직하게 결측을 알린다(가짜 값 금지).
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators import fs_indicators as fs
from config.settings import DOCS_DIR
from utils.jsonio import save_json


def build(code: str, name: str, market: str, financials: dict | None,
          close_price: float | None, source: str) -> dict:
    financials = financials or {}
    return {
        "code": code,
        "name": name,
        "market": market,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": source if financials else "none",
        "growth": fs.revenue_growth(financials),
        "profitability": fs.operating_margin(financials),
        "stability": fs.debt_ratio(financials),
        "cashflow": fs.free_cash_flow(financials),
        "valuation": fs.valuation_per(financials, close_price),
    }


def persist(code: str, body: dict) -> None:
    save_json(DOCS_DIR / "data" / "financials" / f"{code}.json", body)
