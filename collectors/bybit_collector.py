"""BYBIT REST API v5 수집 — 암호화폐 지갑 잔고(design/20 Phase 8).

⚠ 이 세션 환경에는 BYBIT_API_KEY/SECRET이 없어 실제 API 응답으로 검증하지 못했다. HMAC 서명
방식·엔드포인트·응답 필드명은 Bybit v5 공식 문서 기준으로 작성했으나, 실계좌 연동 전 반드시
라이브 재검증이 필요하다(collectors/kis_collector.py와 동일한 미검증 고지).

무료 키 발급 필요(https://www.bybit.com, API Management). 미설정 시 skipped(결측 문법).
"""
from __future__ import annotations

import hashlib
import hmac
import time

from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET
from utils.logging import get_logger

log = get_logger("collectors.bybit")

_BASE_URL = "https://api.bybit.com"
_WALLET_BALANCE_PATH = "/v5/account/wallet-balance"
_RECV_WINDOW = "5000"


def enabled() -> bool:
    return bool(BYBIT_API_KEY and BYBIT_API_SECRET)


def _sign(timestamp: str, query_string: str) -> str:
    """Bybit v5 서명 — HMAC-SHA256(secret, timestamp + api_key + recv_window + queryString)."""
    payload = f"{timestamp}{BYBIT_API_KEY}{_RECV_WINDOW}{query_string}"
    return hmac.new(BYBIT_API_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def collect_wallet_balance() -> dict | None:
    """{"total_equity_usd": float, "coins": [{"coin","wallet_balance","usd_value"}, ...]} | None."""
    if not enabled():
        return None
    try:
        import requests

        query_string = "accountType=UNIFIED"
        timestamp = str(int(time.time() * 1000))
        headers = {
            "X-BAPI-API-KEY": BYBIT_API_KEY,
            "X-BAPI-SIGN": _sign(timestamp, query_string),
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": _RECV_WINDOW,
        }
        r = requests.get(f"{_BASE_URL}{_WALLET_BALANCE_PATH}?{query_string}", headers=headers, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("retCode") != 0:
            log.warning("BYBIT 잔고 조회 실패: %s", body.get("retMsg"))
            return None
        account = (body.get("result", {}).get("list") or [{}])[0]
        coins = [
            {"coin": c.get("coin"), "wallet_balance": float(c.get("walletBalance") or 0),
             "usd_value": float(c.get("usdValue") or 0)}
            for c in account.get("coin", [])
        ]
        return {"total_equity_usd": float(account.get("totalEquity") or 0), "coins": coins}
    except Exception as exc:  # noqa: BLE001
        log.warning("BYBIT 잔고 수집 실패: %s", exc)
        return None
