"""검증된 KOSPI 일봉 → 기술 지표 계산 + docs/data/ta/preview.json 기록(Envelope 컨테이너).

as_of_iso는 수집(빌드) 시각이 아니라 **최신 봉의 거래일 + KRX 정규장 마감 시각**이다(S3 원칙 —
데이터의 진짜 기준시각). 그래야 "전일 정규장 종가 기준" 캡션과 신선도 나이 계산이 일치한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators import ta_indicators as ta
from config.calendar import SESSIONS
from config.freshness import THRESHOLDS
from config.settings import DOCS_DIR, TIMEZONE
from utils.jsonio import save_json

_EXPECTED_T_MIN = 24 * 60
_FRESH_MAX_MIN, _STALE_MIN_MIN = THRESHOLDS["ta_eod"]


def _as_of_iso(latest_date: str) -> str:
    hh, mm = (int(x) for x in SESSIONS["kr"].regular_close.split(":"))
    dt = datetime.strptime(latest_date, "%Y-%m-%d").replace(hour=hh, minute=mm, tzinfo=TIMEZONE)
    return dt.astimezone(timezone.utc).isoformat()


def _envelope(as_of: str, value, unit: str, change_abs=None, change_pct=None, label: str = "", ref_price=None) -> dict:
    e = {
        "value": value,
        "change_abs": change_abs,
        "change_pct": change_pct,
        "unit": unit,
        "as_of_iso": as_of,
        "source": "yahoo",
        "session_key": "none",  # 세션 무관 배치 데이터(design/07 §3-5)
        "expected_T_min": _EXPECTED_T_MIN,
        "freshness_basis": "as_of",
        "label": label,
    }
    if ref_price is not None:
        e["ref_price"] = ref_price
    return e


def sparkline_svg(closes: list[float], width: int = 952, height: int = 72) -> str:
    """60일 종가 인라인 SVG 폴리라인(단색, 수십 바이트 규모 — design/22 §9-2). hex 리터럴 없음(R6)."""
    pts = closes[-60:] if len(closes) > 60 else closes
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    coords = " ".join(
        f"{i * step:.1f},{height - ((v - lo) / span) * height:.1f}" for i, v in enumerate(pts)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="60일 KOSPI 종가 추이" class="v2-ta-spark">'
        f'<polyline points="{coords}" fill="none" stroke="var(--market-flat)" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def build(rows: list[dict]) -> dict:
    """rows: [{'date': 'YYYY-MM-DD', 'close': float}, ...] 오름차순(검증 완료)."""
    closes = [r["close"] for r in rows]
    latest = rows[-1]
    prev_close = rows[-2]["close"] if len(rows) >= 2 else None

    close = latest["close"]
    ma20 = ta.sma(closes, 20)
    dev20 = ta.deviation_pct(close, ma20)
    rsi14 = ta.rsi(closes, 14)
    trend = ta.trend_label(closes, 60)

    as_of = _as_of_iso(latest["date"])
    change_abs = (close - prev_close) if prev_close is not None else None
    change_pct = round((close / prev_close - 1) * 100, 2) if prev_close else None

    return {
        "close": _envelope(as_of, close, "pt", change_abs, change_pct, ref_price=prev_close),
        "deviation_20d": _envelope(as_of, dev20, "%"),
        "rsi_14": _envelope(as_of, rsi14, "x", label=ta.rsi_label(rsi14)),
        "trend_60d": _envelope(as_of, None, "", label=trend or "—"),
    }


def freshness_attrs(as_of_iso: str) -> dict:
    return {
        "as_of_iso": as_of_iso,
        "fresh_max_min": _FRESH_MAX_MIN,
        "stale_min_min": _STALE_MIN_MIN,
        "session_key": "none",
    }


def persist(body: dict) -> None:
    save_json(DOCS_DIR / "data" / "ta" / "preview.json", body)
