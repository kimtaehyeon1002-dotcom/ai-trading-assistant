"""Kiwoom 야간선물 — 데스크톱(kiwoom_desktop)이 기록한 캐시 파일을 읽는다.

CI(리눅스)에서는 Kiwoom OCX 실행 불가 → 캐시 경유가 유일한 경로. 캐시는 git에 커밋되는
data/cache/ 에 둔다(gitignored cache/에 쓰면 CI가 영영 못 읽는다). 신선도 판정은
validators/market_validator.py 책임(여기는 다운로드/읽기만).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config.settings import DATA_CACHE_DIR
from utils.jsonio import load_json, save_json

_CACHE = DATA_CACHE_DIR / "kiwoom_night.json"
LABELS = {"kospi_night": "코스피200 야간선물", "kosdaq_night": "코스닥150 야간선물"}


def collect() -> dict[str, dict | None]:
    """{'kospi_night': raw|None, 'kosdaq_night': raw|None} — raw: {price, change_pct, as_of, source}."""
    data = load_json(_CACHE, default={}) or {}
    out: dict[str, dict | None] = {}
    for key in LABELS:
        e = data.get(key)
        out[key] = {**e, "source": "kiwoom"} if isinstance(e, dict) else None
    return out


def save_day_close(trading_day: str, quotes: dict[str, float]) -> None:
    """당일 정규장 종가 스냅샷 저장 — 그날 밤 등락률의 기준가(design/27).

    trading_day("YYYY-MM-DD")를 함께 박는 것이 핵심이다. 날짜 없이 값만 두면 수집을 하루
    거른 날 **어제 종가**를 오늘 밤의 기준으로 삼게 되는데, 그것이 애초에 고치려던 결함
    (기준가가 하루 밀림)과 정확히 같은 실패다.
    """
    data = load_json(_CACHE, default={}) or {}
    data["day_close"] = {
        "trading_day": trading_day,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "quotes": {k: v for k, v in quotes.items() if isinstance(v, (int, float)) and v > 0},
    }
    save_json(_CACHE, data)


def load_day_close(trading_day: str) -> dict[str, float]:
    """{'kospi_night': 종가, ...} — 기준 거래일이 일치할 때만. 어긋나면 {}(폴백 유도)."""
    entry = (load_json(_CACHE, default={}) or {}).get("day_close")
    if not isinstance(entry, dict) or entry.get("trading_day") != trading_day:
        return {}
    quotes = entry.get("quotes")
    return quotes if isinstance(quotes, dict) else {}


def save_night_futures(kospi: dict | None = None, kosdaq: dict | None = None) -> None:
    """데스크톱(Kiwoom 로그인 환경)에서 호출. 인자 예: {'price': 345.2, 'change_pct': 0.4}"""
    now = datetime.now(timezone.utc).isoformat()
    data = load_json(_CACHE, default={}) or {}
    if kospi:
        data["kospi_night"] = {**kospi, "as_of": now}
    if kosdaq:
        data["kosdaq_night"] = {**kosdaq, "as_of": now}
    data.pop("last_skip", None)  # 갱신 성공 — 직전 스킵 사유는 더 이상 유효하지 않다
    save_json(_CACHE, data)


def save_skip_reason(reason: str) -> None:
    """시세를 갱신하지 못한 사유를 기록(값은 건드리지 않는다) — design/23 P2 진단용.

    "값이 왜 어제 것 그대로인가"의 답이 로그 파일에만 있으면 CI/리포트 쪽에서 확인할 수
    없어, 값과 같은 캐시 파일에 마지막 스킵 사유·시각을 남긴다.
    """
    data = load_json(_CACHE, default={}) or {}
    data["last_skip"] = {"reason": reason, "at": datetime.now(timezone.utc).isoformat()}
    save_json(_CACHE, data)
