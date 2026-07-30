"""BYBIT REST API v5 수집 — 암호화폐 지갑 잔고(design/20 Phase 8).

2026-07-30 실키 검증 완료. HMAC 서명·엔드포인트·응답 필드는 실응답으로 확인했다.

⚠ 시계 동기화가 이 수집기의 실질적 실패 지점이다. Bybit은 `X-BAPI-TIMESTAMP`가 서버 시각보다
**미래이면 recv_window와 무관하게 거부**한다(재전송 공격 방지). 실제 사고: 로컬 시계가 서버보다
약 1초 빨라서 `invalid request, please check your server timestamp or recv_window param:
req_timestamp[...],server_timestamp[...]`로 매 실행 결측이었다 — Windows 기본 시계는 수 초까지
흔히 어긋나므로 로컬 시계를 그대로 믿으면 안 된다. 그래서 공개 엔드포인트(/v5/market/time)로
서버와의 편차를 1회 측정해 보정한 타임스탬프를 쓴다(측정 실패 시에만 로컬 시계로 폴백).

이 API가 **주지 않는 값**(2026-07-31 실응답 키셋 확인 — 버그가 아니라 구조적 결측):
  · 매입단가/매입금액 — wallet-balance에 필드 자체가 없다. 현물 평균단가가 필요하면
    체결내역(/v5/execution/list)을 따로 받아 직접 계산해야 한다.
  · 현물 평가손익 — 위 매입단가가 없으니 파생 불가. `unrealisedPnl`·`totalPerpUPL`은
    **선물 포지션 전용**이라 현물만 보유하면 0으로 온다(0을 '손익 0원'으로 표시하지 않고
    결측 처리한다).
  · 예수금 — `totalAvailableBalance`가 빈 문자열로 온다. 마진 계열 필드(accountIMRate·
    totalMarginBalance 등)가 모두 빈값인 계정 상태와 함께 나타난다.
반대로 확보되는 값: totalEquity·totalWalletBalance·totalPerpUPL, 코인별 walletBalance·
usdValue·equity. **현재가는 usdValue/walletBalance로 파생**한다(응답 안의 값만으로 계산).

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


def _f(raw) -> float | None:
    """빈 문자열·None을 0이 아니라 결측(None)으로 강등한다 — Bybit은 미해당 필드를 ''로 준다."""
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _nonzero(raw) -> float | None:
    """0도 결측으로 본다 — 해당 없음(현물만 보유 시 선물 손익 0)을 '손익 0원'으로 표시하지 않는다."""
    v = _f(raw)
    return v if v else None


def _coin(c: dict) -> dict:
    """코인 1종. **매입단가는 이 엔드포인트에 존재하지 않는다**(실측 키셋 확인) —

    현물 평균단가는 체결내역(/v5/execution/list)을 따로 받아 직접 계산해야 하므로, 여기서는
    결측으로 남긴다. 대신 평가금액/보유수량으로 **평가 단가**는 파생할 수 있다(마크 가격과 동일).
    """
    qty = _f(c.get("walletBalance"))
    usd = _f(c.get("usdValue"))
    return {
        "coin": c.get("coin"),
        "wallet_balance": qty,
        "usd_value": usd,
        "equity": _f(c.get("equity")),
        # 평가 단가 = 평가금액 / 수량. 계산 근거가 둘 다 있을 때만 만든다.
        "price_usd": round(usd / qty, 8) if usd is not None and qty else None,
        # 현물 보유에는 미실현손익 개념이 없어 대개 빈값으로 온다(파생 포지션이 있을 때만 채워짐).
        "unrealised_pnl_usd": _nonzero(c.get("unrealisedPnl")),
    }


def _sign(timestamp: str, query_string: str) -> str:
    """Bybit v5 서명 — HMAC-SHA256(secret, timestamp + api_key + recv_window + queryString)."""
    payload = f"{timestamp}{BYBIT_API_KEY}{_RECV_WINDOW}{query_string}"
    return hmac.new(BYBIT_API_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def collect_wallet_balance() -> dict | None:
    """지갑 잔고 — 실패·미설정 시 None(결측 문법).

    반환 필드는 _coin()/아래 return 참조. **평가손익·매입단가는 이 API가 주지 않는다** —
    없는 값을 만들지 않고 결측으로 남기므로 화면에서 해당 행이 생략된다(가짜 데이터 금지).
    """
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
        coins = [_coin(c) for c in account.get("coin", [])]
        return {
            "total_equity_usd": _f(account.get("totalEquity")),
            # 현금성(주문 가능) 잔고 — design/09 Compact 카드의 예수금 자리.
            "available_usd": _f(account.get("totalAvailableBalance")),
            # 무기한 선물 미실현손익. 현물만 보유하면 0으로 온다(그 경우 결측으로 강등).
            "unrealised_pnl_usd": _nonzero(account.get("totalPerpUPL")),
            "coins": coins,
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("BYBIT 잔고 수집 실패: %s", exc)
        return None
