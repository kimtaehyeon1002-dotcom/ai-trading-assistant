"""Kiwoom 야간선물 — 데스크톱(kiwoom_desktop)이 기록한 캐시 파일을 읽는다.

CI(리눅스)에서는 Kiwoom OCX 실행 불가 → 캐시 경유가 유일한 경로. 신선도 판정은
validators/market_validator.py 책임(여기는 다운로드/읽기만).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config.settings import CACHE_DIR
from utils.jsonio import load_json, save_json

_CACHE = CACHE_DIR / "kiwoom_night.json"
LABELS = {"kospi_night": "코스피 야간선물", "kosdaq_night": "코스닥 야간선물"}


def collect() -> dict[str, dict | None]:
    """{'kospi_night': raw|None, 'kosdaq_night': raw|None} — raw: {price, change_pct, as_of, source}."""
    data = load_json(_CACHE, default={}) or {}
    out: dict[str, dict | None] = {}
    for key in LABELS:
        e = data.get(key)
        out[key] = {**e, "source": "kiwoom"} if isinstance(e, dict) else None
    return out


def save_night_futures(kospi: dict | None = None, kosdaq: dict | None = None) -> None:
    """데스크톱(Kiwoom 로그인 환경)에서 호출. 인자 예: {'price': 345.2, 'change_pct': 0.4}"""
    now = datetime.now(timezone.utc).isoformat()
    data = load_json(_CACHE, default={}) or {}
    if kospi:
        data["kospi_night"] = {**kospi, "as_of": now}
    if kosdaq:
        data["kosdaq_night"] = {**kosdaq, "as_of": now}
    save_json(_CACHE, data)
