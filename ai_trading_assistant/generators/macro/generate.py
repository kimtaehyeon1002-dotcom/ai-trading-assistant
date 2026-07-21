"""Macroeconomics 생성 → docs/macro/index.html + docs/data/macro/{indicators,calendar}.json.

design/02, design/20 Phase 6(독립 트랙 — 시세 유니버스에 의존하지 않음). FRED/ECOS는 API 키
미설정 시 collectors가 사실대로 None을 반환하고, 이 생성기는 결측을 카드 생략으로 이어간다
(추정·가짜 데이터 금지 원칙 계승).
"""
from __future__ import annotations

from pathlib import Path

from collectors import ecos_collector, fred_collector, upbit_collector
from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from repositories import macro_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst
from validators import macro_validator


def _build_fred() -> dict:
    fallback = {sid: None for sid, _ in fred_collector.SERIES}
    raw = runlog.run_step("Macro FRED", fred_collector.collect, fallback=fallback) or fallback
    out: dict = {}
    for sid, entry in raw.items():
        if not entry:
            out[sid] = None
            continue
        obs = macro_validator.validate_observations(entry.get("observations"))
        out[sid] = {"observations": obs, "next_release": entry.get("next_release")} if obs else None
    return out


def _build_ecos() -> dict | None:
    raw = runlog.run_step("Macro ECOS", ecos_collector.collect, fallback=None)
    if not raw:
        return None
    obs = macro_validator.validate_observations(raw.get("base_rate"))
    return {"base_rate": obs} if obs else None


def _build_upbit() -> dict | None:
    return runlog.run_step("Macro Upbit", upbit_collector.collect_btc_krw, fallback=None)


def generate() -> Path:
    fred_data = _build_fred()
    ecos_data = _build_ecos()
    upbit_data = _build_upbit()
    market = pipelines.get_market()  # Phase 3 확장 유니버스의 btc/usdkrw 재사용(김치 프리미엄 재료)

    indicators = macro_repository.build_indicators(fred_data)
    indicators["BOK_BASE_RATE"] = macro_repository.build_base_rate(ecos_data)
    indicators["BTC_KRW"] = macro_repository.build_btc(upbit_data, market)
    calendar = macro_repository.build_calendar(fred_data)
    macro_repository.persist(indicators, calendar)

    ctx = {
        "root": "..",
        "nav": nav.context(active="macro"),
        "generated_at": fmt_kst(now_kst()) + " KST",
        "indicators": indicators,
        "fred_labels": dict(fred_collector.SERIES),
        "fred_series": [sid for sid, _ in fred_collector.SERIES],
        "calendar_events": calendar["events"],
        "freshness": macro_repository.freshness_attrs(),
        "fred_enabled": fred_collector.enabled(),
        "ecos_enabled": ecos_collector.enabled(),
    }
    return render("pages/macro.html", ctx, DOCS_DIR / "macro" / "index.html")
