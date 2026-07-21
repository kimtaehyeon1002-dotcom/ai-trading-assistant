"""SEC EDGAR 재무제표 수집 — companyfacts API(design/20 Phase 7, design/21 §226).

키가 필요 없다(User-Agent 헤더만 요구 — SEC 개발자 가이드). DART와 달리 항상 활성화된다.
us-gaap 개념(태그)명은 기업마다 다를 수 있어 후보 목록 순으로 폴백한다(design/21 §159와
동일한 결측 허용 정신 — 후보를 전부 못 찾으면 해당 라인만 빈 리스트).

실측 확인(2026-07-21, AAPL CIK 0000320193):
- duration 계정(매출·이익 등)은 form="10-K" + frame이 "CY{연도}"(분기 접미사 없음)일 때만 연간
  값이다. frame이 없는 항목은 (end-start) 350~380일로 근사 판별한다.
- instant 계정(자산 등)은 frame 신뢰 불가(같은 10-K에 당기말·전기말이 섞여 나옴) — form="10-K"
  전체를 end 기준으로 묶고 filed가 가장 최신인 값을 채택한다.
"""
from __future__ import annotations

import re
from datetime import datetime

from config.settings import EDGAR_USER_AGENT
from utils.logging import get_logger

log = get_logger("collectors.edgar")

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")

_CONCEPTS: dict[str, list[str]] = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "operating_cf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsForCapitalExpenditures", "PaymentsToAcquirePropertyPlantAndEquipment"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
}
_INSTANT_KEYS = {"assets", "liabilities", "equity"}

_memo_cik_map: dict[str, str] | None = None


def _headers() -> dict:
    return {"User-Agent": EDGAR_USER_AGENT}


def collect_cik_map() -> dict[str, str] | None:
    """{ticker: 10자리 zero-padded CIK}. 실행당 1회만 다운로드(메모이즈)."""
    global _memo_cik_map
    if _memo_cik_map is not None:
        return _memo_cik_map
    try:
        import requests

        r = requests.get(_TICKER_MAP_URL, headers=_headers(), timeout=20)
        r.raise_for_status()
        _memo_cik_map = {row["ticker"]: str(row["cik_str"]).zfill(10) for row in r.json().values()}
    except Exception as exc:  # noqa: BLE001
        log.warning("EDGAR CIK 매핑 수집 실패: %s", exc)
        _memo_cik_map = None
    return _memo_cik_map


def _is_annual_duration(entry: dict) -> bool:
    frame = entry.get("frame", "")
    if _ANNUAL_FRAME.match(frame):
        return True
    if frame:
        return False  # 분기 등 다른 frame이 명시된 경우
    try:
        days = (datetime.fromisoformat(entry["end"]) - datetime.fromisoformat(entry["start"])).days
        return 350 <= days <= 380
    except (KeyError, ValueError):
        return False


def _dedup_by_end(entries: list[dict]) -> list[dict]:
    by_end: dict[str, dict] = {}
    for e in entries:
        prev = by_end.get(e["end"])
        if not prev or e["filed"] > prev["filed"]:
            by_end[e["end"]] = e
    return sorted(({"year": e["end"][:4], "value": e["val"]} for e in by_end.values()), key=lambda r: r["year"])


def _extract(facts: dict, line: str) -> list[dict]:
    """후보 개념을 전부 계산해 **가장 최신 연도를 포함하는** 시리즈를 채택한다.

    실측 확인(2026-07-21, AAPL): "Revenues" 개념은 2016~2018년만 태깅되어 있고(ASC 606 도입 후
    폐기), 실제 최신 데이터는 "RevenueFromContractWithCustomerExcludingAssessedTax"에 있다 —
    첫 매칭 후보를 즉시 채택하면 오래된 3개년만 얻는 조용한 실패가 된다. 최신 연도 기준으로
    후보들을 비교해야 한다.
    """
    gaap = facts.get("facts", {}).get("us-gaap", {})
    best: list[dict] = []
    for concept in _CONCEPTS[line]:
        node = gaap.get(concept)
        if not node:
            continue
        units = node.get("units", {})
        unit_key = next(iter(units), None)
        if not unit_key:
            continue
        entries = units[unit_key]
        annual = [
            e for e in entries
            if e.get("form") == "10-K" and (line in _INSTANT_KEYS or _is_annual_duration(e))
        ]
        series = _dedup_by_end(annual)
        if series and (not best or series[-1]["year"] > best[-1]["year"]):
            best = series
    return best


def collect_company_facts(cik: str) -> dict[str, list[dict]] | None:
    """{line: [{'year','value'}, ...]} 9개 라인 — 개념 전부 결측이면 해당 라인만 빈 리스트."""
    try:
        import requests

        r = requests.get(_FACTS_URL.format(cik=cik), headers=_headers(), timeout=20)
        r.raise_for_status()
        facts = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("EDGAR companyfacts 수집 실패(CIK=%s): %s", cik, exc)
        return None
    return {line: _extract(facts, line) for line in _CONCEPTS}
