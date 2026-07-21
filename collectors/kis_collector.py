"""한국투자증권(KIS) Open API 수집 — 위탁(미국주식)·ISA(ETF) 계좌 잔고(design/20 Phase 8).

⚠ 이 세션 환경에는 KIS_APP_KEY/SECRET/계좌번호가 없어 실제 API 응답으로 검증하지 못했다.
엔드포인트·tr_id·응답 필드명은 KIS Open API 공식 문서 기준으로 작성했으나, 실계좌 연동 전
반드시 라이브 재검증이 필요하다(design/21 §226 "공식 아님" 경고와 별개로, 이 필드 스키마
자체의 실측 확인이 아직 없다는 뜻 — collectors/dart_collector.py와 동일한 미검증 고지).

무료 키 발급 필요(https://apiportal.koreainvestment.com). 미설정 시 skipped(결측 문법).
"""
from __future__ import annotations

import time

from config.settings import KIS_ACCOUNT_FOREIGN, KIS_ACCOUNT_ISA, KIS_APP_KEY, KIS_APP_SECRET
from utils.logging import get_logger

log = get_logger("collectors.kis")

_BASE_URL = "https://openapi.koreainvestment.com:9443"
_TOKEN_URL = f"{_BASE_URL}/oauth2/tokenP"
# 해외주식 잔고조회(위탁, 미국주식): tr_id 실전투자 기준(KIS 공식 문서, 미검증)
_OVERSEAS_BALANCE_URL = f"{_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
_OVERSEAS_TR_ID = "TTTS3012R"
# 국내주식 잔고조회(ISA, ETF): tr_id 실전투자 기준(KIS 공식 문서, 미검증)
_DOMESTIC_BALANCE_URL = f"{_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
_DOMESTIC_TR_ID = "TTTC8434R"

_memo_token: dict | None = None  # {"token": str, "expires_at": epoch}


def enabled() -> bool:
    return bool(KIS_APP_KEY and KIS_APP_SECRET)


def _get_token() -> str | None:
    """OAuth2 접근토큰 — 만료 전까지 재사용(불필요한 재발급은 KIS 정책상 제한될 수 있음)."""
    global _memo_token
    if _memo_token and _memo_token["expires_at"] > time.time() + 60:
        return _memo_token["token"]
    if not enabled():
        return None
    try:
        import requests

        r = requests.post(_TOKEN_URL, json={
            "grant_type": "client_credentials", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET,
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        token = body.get("access_token")
        if not token:
            return None
        expires_in = int(body.get("expires_in", 86400))
        _memo_token = {"token": token, "expires_at": time.time() + expires_in}
        return token
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS 토큰 발급 실패: %s", exc)
        return None


def _headers(token: str, tr_id: str) -> dict:
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": tr_id,
    }


def collect_overseas_balance() -> dict | None:
    """위탁(미국주식) 잔고 — {"holdings": [...], "summary": {...}} | None(미설정·실패)."""
    token = _get_token()
    if not token or not KIS_ACCOUNT_FOREIGN:
        return None
    try:
        import requests

        acct = KIS_ACCOUNT_FOREIGN
        r = requests.get(_OVERSEAS_BALANCE_URL, headers=_headers(token, _OVERSEAS_TR_ID), params={
            "CANO": acct[:8], "ACNT_PRDT_CD": acct[8:10], "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD", "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("rt_cd") != "0":
            log.warning("KIS 해외잔고 조회 실패: %s", body.get("msg1"))
            return None
        summary = body.get("output2", [{}])[0]
        # 필드명은 KIS 공식 문서 기준(미검증) — frcr_evlu_tota(외화평가총액), evlu_pfls_amt(평가손익)
        return {
            "holdings": body.get("output1", []),
            "summary": summary,
            "usd_value": _to_float(summary.get("frcr_evlu_tota")),
            "eval_pnl_usd": _to_float(summary.get("ovrs_tot_pfls")),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS 해외잔고 수집 실패: %s", exc)
        return None


def collect_isa_balance() -> dict | None:
    """ISA(ETF) 잔고 — {"holdings": [...], "summary": {...}} | None(미설정·실패)."""
    token = _get_token()
    if not token or not KIS_ACCOUNT_ISA:
        return None
    try:
        import requests

        acct = KIS_ACCOUNT_ISA
        r = requests.get(_DOMESTIC_BALANCE_URL, headers=_headers(token, _DOMESTIC_TR_ID), params={
            "CANO": acct[:8], "ACNT_PRDT_CD": acct[8:10],
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("rt_cd") != "0":
            log.warning("KIS ISA잔고 조회 실패: %s", body.get("msg1"))
            return None
        summary = body.get("output2", [{}])[0]
        # 필드명은 KIS 공식 문서 기준(미검증) — tot_evlu_amt(총평가금액), evlu_pfls_smtl_amt(평가손익합계)
        return {
            "holdings": body.get("output1", []),
            "summary": summary,
            "krw_value": _to_float(summary.get("tot_evlu_amt")),
            "eval_pnl_krw": _to_float(summary.get("evlu_pfls_smtl_amt")),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS ISA잔고 수집 실패: %s", exc)
        return None


def _to_float(raw) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return None
