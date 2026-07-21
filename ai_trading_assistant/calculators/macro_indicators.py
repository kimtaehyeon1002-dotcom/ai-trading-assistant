"""거시지표 순수 계산 — YoY 변화·김치 프리미엄. 입력은 검증된 관측치(계산 로직만, 수집 없음)."""
from __future__ import annotations

from datetime import date


def yoy_change(observations: list[dict]) -> dict | None:
    """최신 관측치 vs 정확히 12개월 전 같은 월 관측치. observations: [{'date','value'}, ...] 오름차순.

    분기 지표(GDP)도 "같은 월"로 매칭하면 자동으로 "같은 분기, 1년 전"이 된다.
    12개월 전 관측치가 없으면(데이터 부족) None — 억지 근사 금지.
    """
    if len(observations) < 2:
        return None
    latest = observations[-1]
    latest_date = date.fromisoformat(latest["date"])
    target_year = latest_date.year - 1
    for obs in observations:
        d = date.fromisoformat(obs["date"])
        if d.year == target_year and d.month == latest_date.month:
            prior_value = obs["value"]
            if not prior_value:
                return None
            change_abs = round(latest["value"] - prior_value, 4)
            change_pct = round((latest["value"] / prior_value - 1) * 100, 2)
            return {
                "change_abs": change_abs,
                "change_pct": change_pct,
                "prior_value": prior_value,
                "prior_date": obs["date"],
            }
    return None


def kimchi_premium_pct(btc_krw: float | None, btc_usd: float | None, usdkrw: float | None) -> float | None:
    """(BTC/KRW 실거래가 ÷ (BTC/USD × USD/KRW 환산가) − 1) × 100. 재료 중 하나라도 없으면 None."""
    if not btc_krw or not btc_usd or not usdkrw:
        return None
    implied_krw = btc_usd * usdkrw
    if not implied_krw:
        return None
    return round((btc_krw / implied_krw - 1) * 100, 2)
