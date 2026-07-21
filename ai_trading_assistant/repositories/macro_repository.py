"""검증된 거시 관측치 → Envelope 빌드 + docs/data/macro/{indicators,calendar}.json 기록.

Envelope의 change_abs/change_pct는 직전 관측치 대비(전월비 등) 변화이며, 전년동월비(YoY)는
별도 "yoy" 필드로 분리한다(design/20 Phase 6, calculators/macro_indicators.yoy_change 사용).
as_of_iso는 관측 대상 기간이 아니라 "이 값이 마지막으로 확인된 시각"(수집/빌드 시각)이다 —
발표 주기가 불규칙한 지표 특성상 이렇게 해야 "재확인한 지 얼마나 됐는가"를 정직하게 반영한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from calculators.macro_indicators import kimchi_premium_pct, yoy_change
from collectors.fred_collector import SERIES as FRED_SERIES
from config.consensus import CONSENSUS
from config.economic_calendar import FOMC_2026, FOMC_STATEMENT_TIME_ET
from config.freshness import THRESHOLDS
from config.settings import DOCS_DIR
from utils.jsonio import save_json

_FRESH_MAX_MIN, _STALE_MIN_MIN = THRESHOLDS["macro"]
_EXPECTED_T_MIN = 60
_LABELS = dict(FRED_SERIES)


def _envelope(as_of: str, value: float, change_abs, change_pct, label: str) -> dict:
    return {
        "value": value,
        "change_abs": change_abs,
        "change_pct": change_pct,
        "unit": "%" if change_pct is not None and abs(value) < 100 else "pt",
        "as_of_iso": as_of,
        "source": "fred",
        "session_key": "none",
        "expected_T_min": _EXPECTED_T_MIN,
        "freshness_basis": "as_of",
        "label": label,
    }


def build_indicators(fred_data: dict[str, dict | None]) -> dict:
    """fred_data: fred_collector.collect() 형태 {series_id: {'observations','next_release'}|None}."""
    as_of = datetime.now(timezone.utc).isoformat()
    out: dict = {}
    for series_id, label in FRED_SERIES:
        entry = fred_data.get(series_id)
        if not entry or not entry.get("observations"):
            out[series_id] = None
            continue
        obs = entry["observations"]
        latest = obs[-1]
        prior = obs[-2] if len(obs) >= 2 else None
        change_abs = round(latest["value"] - prior["value"], 4) if prior else None
        change_pct = round((latest["value"] / prior["value"] - 1) * 100, 2) if prior and prior["value"] else None

        item: dict = {
            "envelope": _envelope(as_of, latest["value"], change_abs, change_pct, label),
            "yoy": yoy_change(obs),
            "next_release": entry.get("next_release"),
        }
        if series_id in CONSENSUS:
            item["consensus"] = CONSENSUS[series_id]
        out[series_id] = item
    return out


def build_base_rate(ecos_data: dict | None) -> dict | None:
    """ecos_collector.collect() 결과 → Envelope 래퍼. 재료 없으면 None(결측 문법)."""
    if not ecos_data or not ecos_data.get("base_rate"):
        return None
    obs = ecos_data["base_rate"]
    latest, prior = obs[-1], (obs[-2] if len(obs) >= 2 else None)
    change_abs = round(latest["value"] - prior["value"], 4) if prior else None
    as_of = datetime.now(timezone.utc).isoformat()
    env = _envelope(as_of, latest["value"], change_abs, None, "한국은행 기준금리")
    env["unit"], env["source"] = "%", "ecos"
    return {"envelope": env, "yoy": None, "next_release": None}


def build_btc(upbit_data: dict | None, market: dict) -> dict | None:
    """upbit_collector.collect_btc_krw() 결과 + market.json(Phase 3 btc/usdkrw)으로 김치 프리미엄 산출."""
    if not upbit_data:
        return None
    as_of = datetime.now(timezone.utc).isoformat()
    change_abs = upbit_data["price"] - upbit_data["previous_close"] if upbit_data.get("previous_close") else None
    env = _envelope(as_of, upbit_data["price"], change_abs, upbit_data.get("change_pct"), "비트코인(KRW)")
    env["unit"], env["source"], env["session_key"] = "KRW", "upbit", "crypto_24h"

    btc_usd_q = market.get("btc")
    usdkrw_q = market.get("usdkrw")
    premium = kimchi_premium_pct(
        upbit_data["price"],
        btc_usd_q.price if btc_usd_q else None,
        usdkrw_q.price if usdkrw_q else None,
    )
    return {"envelope": env, "yoy": None, "next_release": None, "kimchi_premium_pct": premium}


def _event_at_utc(date_str: str, time_str: str | None, tz_name: str | None) -> str | None:
    """지역 날짜+시각+IANA 타임존 → UTC ISO. 서머타임(EDT/EST)은 zoneinfo가 날짜별로 정확히
    처리한다 — 템플릿에서 고정 오프셋 문자열을 하드코딩하면 DST 전환 시점에 틀린다."""
    if not time_str:
        return None
    try:
        hh, mm = (int(x) for x in time_str.split(":"))
        naive = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hh, minute=mm)
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
        return naive.replace(tzinfo=tz).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def build_calendar(fred_data: dict[str, dict | None]) -> dict:
    events: list[dict] = []
    for date_str, label in FOMC_2026:
        event = {
            "date": date_str, "time": FOMC_STATEMENT_TIME_ET, "timezone": "America/New_York",
            "label": label, "source": "fomc",
        }
        at_utc = _event_at_utc(date_str, FOMC_STATEMENT_TIME_ET, "America/New_York")
        if at_utc:
            event["event_at_utc"] = at_utc
        events.append(event)
    for series_id, label in FRED_SERIES:
        entry = fred_data.get(series_id)
        next_release = entry.get("next_release") if entry else None
        if next_release:
            events.append({
                "date": next_release, "time": None, "timezone": None,
                "label": f"{label} 발표", "source": "fred", "series_id": series_id,
            })
    events.sort(key=lambda e: e["date"])
    return {"as_of": datetime.now(timezone.utc).isoformat(), "events": events}


def persist(indicators: dict, calendar: dict) -> None:
    save_json(DOCS_DIR / "data" / "macro" / "indicators.json", indicators)
    save_json(DOCS_DIR / "data" / "macro" / "calendar.json", calendar)


def freshness_attrs() -> dict:
    return {"fresh_max_min": _FRESH_MAX_MIN, "stale_min_min": _STALE_MIN_MIN}
