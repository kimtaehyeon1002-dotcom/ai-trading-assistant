"""BYBIT REST API v5 수집 — 암호화폐 지갑 잔고(design/20 Phase 8).

2026-07-30 실키 검증 완료. HMAC 서명·엔드포인트·응답 필드는 실응답으로 확인했다.

⚠ 시계 동기화가 이 수집기의 실질적 실패 지점이다. Bybit은 `X-BAPI-TIMESTAMP`가 서버 시각보다
**미래이면 recv_window와 무관하게 거부**한다(재전송 공격 방지). 실제 사고: 로컬 시계가 서버보다
약 1초 빨라서 `invalid request, please check your server timestamp or recv_window param:
req_timestamp[...],server_timestamp[...]`로 매 실행 결측이었다 — Windows 기본 시계는 수 초까지
흔히 어긋나므로 로컬 시계를 그대로 믿으면 안 된다. 그래서 공개 엔드포인트(/v5/market/time)로
서버와의 편차를 1회 측정해 보정한 타임스탬프를 쓴다(측정 실패 시에만 로컬 시계로 폴백).

무료 키 발급 필요(https://www.bybit.com, API Management). 키 타입은 **HMAC**(RSA 아님),
권한은 조회만 필요하므로 Read-Only. 미설정 시 skipped(결측 문법).
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
_SERVER_TIME_PATH = "/v5/market/time"
_RECV_WINDOW = "5000"
# 서버 시각 - 로컬 시각(ms). 실행당 1회 측정해 재사용한다(매 요청 왕복은 낭비).
_clock_offset_ms: int | None = None
# 보정 후에도 살짝 앞서는 것을 막는 안전 여유 — 미래 타임스탬프는 즉시 거부되므로
# 과거 쪽으로 조금 치우치게 둔다(recv_window 5초 안이라 과거 편향은 무해하다).
_SAFETY_LAG_MS = 500


def enabled() -> bool:
    return bool(BYBIT_API_KEY and BYBIT_API_SECRET)


def _server_offset_ms() -> int:
    """Bybit 서버와의 시계 편차(ms). 측정 실패 시 0(로컬 시계 그대로)."""
    global _clock_offset_ms
    if _clock_offset_ms is not None:
        return _clock_offset_ms
    try:
        import requests

        r = requests.get(f"{_BASE_URL}{_SERVER_TIME_PATH}", timeout=10)
        r.raise_for_status()
        server_ms = int(r.json()["result"]["timeNano"]) // 1_000_000
        _clock_offset_ms = server_ms - int(time.time() * 1000)
        if abs(_clock_offset_ms) > 1000:
            log.info("BYBIT 서버와 로컬 시계 편차 %dms — 보정해서 서명한다", _clock_offset_ms)
    except Exception as exc:  # noqa: BLE001 - 편차 측정 실패가 수집 자체를 막지는 않는다
        log.warning("BYBIT 서버 시각 조회 실패(로컬 시계 사용): %s", exc)
        _clock_offset_ms = 0
    return _clock_offset_ms


def _timestamp_ms() -> str:
    return str(int(time.time() * 1000) + _server_offset_ms() - _SAFETY_LAG_MS)


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
        timestamp = _timestamp_ms()
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
