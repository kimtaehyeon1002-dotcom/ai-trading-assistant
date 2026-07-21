"""Upbit 공개 API 수집 — BTC/KRW(김치 프리미엄 산출 재료). 무키·CORS 안정(design/21 §3)."""
from __future__ import annotations

from utils.logging import get_logger

log = get_logger("collectors.upbit")


def collect_btc_krw() -> dict | None:
    """{'price': float, 'change_pct': float, 'prev_closing_price': float} — 실패 시 None."""
    import requests

    try:
        r = requests.get(
            "https://api.upbit.com/v1/ticker", params={"markets": "KRW-BTC"}, timeout=10
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        row = rows[0]
        price = float(row["trade_price"])
        prev = float(row["prev_closing_price"])
        change_pct = round((price / prev - 1) * 100, 2) if prev else None
        return {"price": price, "change_pct": change_pct, "previous_close": prev}
    except Exception as exc:  # noqa: BLE001
        log.warning("Upbit 호출 실패: %s", exc)
        return None
