"""Financial Statements 생성 — 유니버스 종목 5개 지표 카드(design/06, design/20 Phase 7).

design/21 §159(업종 평균 무료 소스 부재)에 맞춰 자사 5년 단독 판정으로 축소하고, 설계 원안
15장 카드도 그룹당 대표 지표 1개(5장)로 1차 축소했다 — 실제로 검증 가능한 무료 데이터
(EDGAR 실측 확인·DART는 키 없이는 미검증)만으로 정직하게 시작한다.

KR은 DART(무료 키 필요, 미설정 시 결측), US는 EDGAR(키 불필요, 상시 활성)를 사용한다. 가격은
이미 발행된 Stock Hub JSON(docs/data/stock/hub/<code>.json)의 종가를 재사용한다 — 이 생성기는
"stock" 타깃 이후 실행돼야 PER이 채워진다(선행 조건, 없으면 PER만 결측).
"""
from __future__ import annotations

from pathlib import Path

from collectors import dart_collector, edgar_collector
from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from repositories import fs_repository
from repositories.stock_repository import KR_MARKETS
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.jsonio import load_json, save_json
from validators import fs_validator


def _universe() -> list[dict]:
    data = load_json(DOCS_DIR / "data" / "stock" / "universe.json", default=[])
    return data if isinstance(data, list) else []


def _close_price(code: str) -> float | None:
    hub = load_json(DOCS_DIR / "data" / "stock" / "hub" / f"{code}.json", default=None)
    if not hub or not hub.get("quote"):
        return None
    return hub["quote"].get("close")


def _build_kr(entries: list[dict]) -> None:
    corp_codes = runlog.run_step("FS DART corpCode", dart_collector.collect_corp_codes, fallback=None)
    year = now_kst().year
    for e in entries:
        raw = None
        corp_code = (corp_codes or {}).get(e["code"])
        if corp_code:
            raw = dart_collector.collect_financials(corp_code, year)
        financials = fs_validator.validate(raw)
        body = fs_repository.build(e["code"], e["name"], e["market"], financials, _close_price(e["code"]), "dart")
        fs_repository.persist(e["code"], body)


def _build_us(entries: list[dict]) -> None:
    cik_map = runlog.run_step("FS EDGAR CIK맵", edgar_collector.collect_cik_map, fallback=None)
    for e in entries:
        raw = None
        cik = (cik_map or {}).get(e["code"])
        if cik:
            raw = edgar_collector.collect_company_facts(cik)
        financials = fs_validator.validate(raw)
        body = fs_repository.build(e["code"], e["name"], e["market"], financials, _close_price(e["code"]), "edgar")
        fs_repository.persist(e["code"], body)


def generate() -> Path:
    universe = _universe()
    kr_entries = [e for e in universe if isinstance(e, dict) and e.get("market") in KR_MARKETS]
    us_entries = [e for e in universe if isinstance(e, dict) and e.get("market") not in KR_MARKETS]

    _build_kr(kr_entries)
    _build_us(us_entries)

    save_json(DOCS_DIR / "data" / "financials" / "index.json",
              [{"code": e["code"], "name": e["name"], "market": e["market"]} for e in universe])

    out = DOCS_DIR / "financials" / "index.html"
    return render(
        "pages/financials.html",
        {
            "root": "..",
            "nav": nav.context(active="financials"),
            "generated_at": fmt_kst(now_kst()) + " KST",
            "universe": universe,
        },
        out,
    )
