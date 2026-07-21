"""FRED(연준 경제데이터) 수집 — CPI/PCE/GDP/UNRATE/PAYEMS 관측치 + 다음 발표일.

FRED_API_KEY 미설정 시 사실대로 None(가짜 데이터 금지). 무료 키 발급: https://fred.stlouisfed.org
API 문서: series/observations(관측치), series/release(계열→release_id), release/dates(발표일).
"""
from __future__ import annotations

from datetime import date

from config.settings import FRED_API_KEY
from utils.logging import get_logger

log = get_logger("collectors.fred")

_BASE = "https://api.stlouisfed.org/fred"

# 표시 순서·라벨(design/21 §2-2 "CPI/PCE/GDP/UNRATE/PAYEMS")
SERIES: list[tuple[str, str]] = [
    ("CPIAUCSL", "CPI(소비자물가지수)"),
    ("PCEPI", "PCE(개인소비지출 물가지수)"),
    ("GDP", "GDP(실질 국내총생산)"),
    ("UNRATE", "실업률"),
    ("PAYEMS", "비농업 고용지수"),
]


def enabled() -> bool:
    return bool(FRED_API_KEY)


def _get(path: str, params: dict) -> dict | None:
    import requests

    try:
        r = requests.get(
            f"{_BASE}/{path}",
            params={**params, "api_key": FRED_API_KEY, "file_type": "json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("FRED 호출 실패 %s: %s", path, exc)
        return None


def collect_observations(series_id: str, limit: int = 14) -> list[dict] | None:
    """[{'date': 'YYYY-MM-DD', 'value': float}, ...] 오름차순(최근 limit개) — 실패 시 None."""
    if not enabled():
        return None
    data = _get("series/observations", {
        "series_id": series_id, "sort_order": "desc", "limit": limit,
    })
    if not data or "observations" not in data:
        return None
    rows = []
    for obs in data["observations"]:
        try:
            rows.append({"date": obs["date"], "value": float(obs["value"])})
        except (KeyError, ValueError, TypeError):
            continue  # "." 등 결측 마커 — 해당 관측치만 건너뜀(가짜 0 금지)
    rows.reverse()  # 오름차순
    return rows or None


def next_release_date(series_id: str) -> str | None:
    """다음 발표 예정일(YYYY-MM-DD) — release_id를 먼저 조회한 뒤 release/dates에서 조회."""
    if not enabled():
        return None
    release = _get("series/release", {"series_id": series_id})
    if not release or not release.get("releases"):
        return None
    release_id = release["releases"][0].get("id")
    if release_id is None:
        return None
    dates_resp = _get("release/dates", {
        "release_id": release_id,
        "include_release_dates_with_no_data": "true",
        "sort_order": "asc",
        "realtime_start": date.today().isoformat(),
    })
    if not dates_resp or not dates_resp.get("release_dates"):
        return None
    return dates_resp["release_dates"][0].get("date")


def collect() -> dict[str, dict | None]:
    """{series_id: {'observations': [...], 'next_release': str|None} | None}."""
    if not enabled():
        log.info("FRED_API_KEY 미설정 — 경제지표 수집 skipped")
        return {sid: None for sid, _ in SERIES}
    out: dict[str, dict | None] = {}
    for sid, _label in SERIES:
        obs = collect_observations(sid)
        if not obs:
            out[sid] = None
            continue
        out[sid] = {"observations": obs, "next_release": next_release_date(sid)}
    return out
