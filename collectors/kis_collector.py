"""한국투자증권(KIS) Open API 수집 — 위탁(미국주식)·ISA(ETF) 계좌 잔고(design/20 Phase 8).

2026-07-26 실키로 위탁(해외) 엔드포인트 1차 검증 완료. 문서 가정과 실측이 두 가지 다름:
① `output2`는 항목에 따라 **단일 dict로 오기도, [dict] 리스트로 오기도 한다** — 위탁(해외)
  잔고(TTTS3012R)는 dict였다. 리스트 전제로 `[0]` 인덱싱하면 `KeyError: 0`으로 조용히 실패한다
  (원래 코드가 이 버그였다 — `_first_row()`로 두 형태를 모두 흡수하도록 고쳤다).
② 위탁(해외) `output2`에는 **총평가금액(USD) 필드 자체가 없다** — 실측 키셋:
  `frcr_pchs_amt1·frcr_buy_amt_smtl1·frcr_buy_amt_smtl2·ovrs_rlzt_pfls_amt·ovrs_rlzt_pfls_amt2·
  ovrs_tot_pfls·rlzt_erng_rt·tot_evlu_pfls_amt·tot_pftrt` — 전부 손익 계열이고 잔고 합계가 없다.
  그래서 `usd_value`는 `output1`(종목별 보유) 각 행의 `ovrs_stck_evlu_amt`를 합산해 구한다.
  종목별 필드(`ovrs_item_name·ovrs_pdno·ovrs_cblc_qty·pchs_avg_pric·now_pric2·ovrs_stck_evlu_amt·
  frcr_evlu_pfls_amt·evlu_pfls_rt`)는 실측 확인됨. ISA(국내, TTTC8434R)는 위 두 가지 구조적
  이슈가 여기도 있을 수 있으니 실측 시 확인할 것.
③ **앱키는 계좌에 묶인다.** 위탁 앱키로 ISA 계좌를 조회하면 상품코드를 01/29/22/03/08/12 무엇으로
  바꿔도 전부 INVALID_CHECK_ACNO로 거부됐다(실측) — 상품코드 문제가 아니라 자격증명 문제다.
  그래서 계좌마다 앱키를 따로 받는다(`_foreign_credentials()` / `_isa_credentials()`).
  토큰 캐시도 앱키별로 분리해야 한다 — 자세한 이유는 `_memo_tokens` 주석 참조.

무료 키 발급 필요(https://apiportal.koreainvestment.com). 미설정 시 skipped(결측 문법).
"""
from __future__ import annotations

import time

from config.settings import (
    KIS_ACCOUNT_FOREIGN,
    KIS_ACCOUNT_ISA,
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_ISA_APP_KEY,
    KIS_ISA_APP_SECRET,
)
from utils.logging import get_logger

log = get_logger("collectors.kis")

_BASE_URL = "https://openapi.koreainvestment.com:9443"
_TOKEN_URL = f"{_BASE_URL}/oauth2/tokenP"
# 해외주식 잔고조회(위탁, 미국주식): tr_id 실전투자 기준(KIS 공식 문서, 미검증)
_OVERSEAS_BALANCE_URL = f"{_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance"
_OVERSEAS_TR_ID = "TTTS3012R"
# 해외주식 체결기준현재잔고 — **외화예수금 확보 경로**(design/25 §8-1).
# TTTS3012R output2에는 예수금 필드가 아예 없다는 것을 실측으로 확인했다(2026-07-29 응답
# 키셋: frcr_pchs_amt1·ovrs_rlzt_pfls_amt·ovrs_tot_pfls·rlzt_erng_rt·tot_evlu_pfls_amt·
# tot_pftrt·frcr_buy_amt_smtl1/2·ovrs_rlzt_pfls_amt2 — 전부 손익 계열). 그래서 기존
# `deposit_usd`는 항상 None이었고, 위탁 계좌 총액이 예수금만큼 통째로 빠져 있었다.
_OVERSEAS_PRESENT_URL = f"{_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-present-balance"
_OVERSEAS_PRESENT_TR_ID = "CTRP6504R"
# 국내주식 잔고조회(ISA, ETF): tr_id 실전투자 기준(KIS 공식 문서, 미검증)
_DOMESTIC_BALANCE_URL = f"{_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
_DOMESTIC_TR_ID = "TTTC8434R"

# 앱키별 토큰 캐시 — {app_key: {"token": str, "expires_at": epoch}}.
# **계좌별로 앱키가 다르므로 토큰도 앱키별로 분리해야 한다.** 전역 단일 캐시(_memo_token)를 쓰면
# 먼저 조회한 계좌의 토큰을 다른 계좌가 물려받아, 그 계좌에는 유효하지 않은 토큰으로 요청하게 된다
# (증상이 '계좌번호 오류'로 나타나 원인 추적이 어렵다).
_memo_tokens: dict[str, dict] = {}


def _foreign_credentials() -> tuple[str, str]:
    return KIS_APP_KEY, KIS_APP_SECRET


def _isa_credentials() -> tuple[str, str]:
    """ISA 전용 앱키. 비어 있으면 공용 키로 폴백(한 앱키에 두 계좌가 묶인 경우 하위 호환)."""
    return (KIS_ISA_APP_KEY or KIS_APP_KEY, KIS_ISA_APP_SECRET or KIS_APP_SECRET)


def enabled() -> bool:
    """어느 한 계좌라도 조회 가능하면 True — 계좌별 자격증명이 독립이므로 개별 함수가 각자 판단한다."""
    return bool((KIS_APP_KEY and KIS_APP_SECRET) or (KIS_ISA_APP_KEY and KIS_ISA_APP_SECRET))


def _split_account(raw: str) -> tuple[str, str]:
    """계좌번호 → (CANO 8자리, ACNT_PRDT_CD 2자리). HTS/앱은 흔히 '12345678-01'처럼

    하이픈을 포함해 표시하는데, 그대로 naive 슬라이싱(acct[:8]/acct[8:10])하면 하이픈이
    상품코드 자리를 차지해 조회가 깨진다 — 숫자만 남기고 나눈다."""
    digits = "".join(c for c in raw if c.isdigit())
    return digits[:8], digits[8:10]


def _first_row(value) -> dict:
    """`output2`는 TR에 따라 단일 dict로도, [dict] 리스트로도 온다(실키로 확인, 위 모듈
    docstring 참조) — 어느 쪽이든 첫 행을 dict로 돌려준다. 둘 다 아니면 빈 dict(결측 문법)."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value:
        return value[0]
    return {}


def _sum_field(rows: list[dict], *candidates: str) -> float | None:
    """summary가 총액을 안 주는 TR(위탁 해외잔고, 실키로 확인)을 위한 대체 경로 —

    종목별 행을 합산해 총평가액을 구한다. 한 건도 못 찾으면 None(결측, 0 아님)."""
    total = 0.0
    found = False
    for row in rows:
        for key in candidates:
            v = _to_float(row.get(key))
            if v is not None:
                total += v
                found = True
                break
    return round(total, 2) if found else None


def _get_token(app_key: str, app_secret: str) -> str | None:
    """OAuth2 접근토큰 — 앱키별로 캐시하고 만료 전까지 재사용한다.

    KIS는 토큰 발급을 **앱키당 1분에 1회**로 제한하므로(EGW00133), 재사용이 선택이 아니라
    필수다. 캐시 키가 앱키인 덕에 계좌별 앱키가 서로의 토큰을 덮어쓰지 않는다."""
    if not (app_key and app_secret):
        return None
    cached = _memo_tokens.get(app_key)
    if cached and cached["expires_at"] > time.time() + 60:
        return cached["token"]
    try:
        import requests

        r = requests.post(_TOKEN_URL, json={
            "grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret,
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        token = body.get("access_token")
        if not token:
            return None
        expires_in = int(body.get("expires_in", 86400))
        _memo_tokens[app_key] = {"token": token, "expires_at": time.time() + expires_in}
        return token
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS 토큰 발급 실패: %s", exc)
        return None


def _headers(token: str, tr_id: str, app_key: str, app_secret: str) -> dict:
    """appkey/appsecret 헤더는 토큰과 **같은 자격증명**이어야 한다 — 섞이면 인증이 깨진다."""
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }


def collect_overseas_balance() -> dict | None:
    """위탁(미국주식) 잔고 — {"holdings": [...], "summary": {...}} | None(미설정·실패)."""
    app_key, app_secret = _foreign_credentials()
    token = _get_token(app_key, app_secret)
    if not token or not KIS_ACCOUNT_FOREIGN:
        return None
    try:
        import requests

        cano, prdt = _split_account(KIS_ACCOUNT_FOREIGN)
        r = requests.get(_OVERSEAS_BALANCE_URL,
                         headers=_headers(token, _OVERSEAS_TR_ID, app_key, app_secret), params={
            "CANO": cano, "ACNT_PRDT_CD": prdt, "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD", "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("rt_cd") != "0":
            log.warning("KIS 해외잔고 조회 실패: %s", body.get("msg1"))
            return None
        summary = _first_row(body.get("output2"))
        holdings = body.get("output1", [])
        # 실측(2026-07-26): output2에 총평가금액 필드가 없다 — 종목별 ovrs_stck_evlu_amt 합산으로 대체.
        usd_value = _pick_float(summary, "frcr_evlu_tota", "evlu_amt_smtl2")
        if usd_value is None:
            usd_value = _sum_field(holdings, "ovrs_stck_evlu_amt")
        # 예수금은 이 TR 응답에 아예 없다(실측) — 별도 TR(CTRP6504R)로 보강한다.
        cash = _collect_overseas_cash(token, app_key, app_secret, cano, prdt)
        return {
            "holdings": holdings,
            "summary": summary,
            # 유가증권 평가액(USD). CTRP6504R 종목합과 일치함을 실측 확인(비율 1.0000).
            "securities_usd": usd_value,
            "usd_value": _add(usd_value, cash.get("deposit_usd")),  # 계좌 총액 = 주식 + 예수금
            "eval_pnl_usd": _to_float(summary.get("ovrs_tot_pfls")),
            "principal_usd": _pick_float(summary, "frcr_pchs_amt1", "pchs_amt_smtl", "frcr_pchs_amt"),
            "deposit_usd": cash.get("deposit_usd"),
            "fx_rate_reported": cash.get("fx_rate"),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS 해외잔고 수집 실패: %s", exc)
        return None


def _add(*values) -> float | None:
    """확보된 값만 더한다. 전부 결측이면 None(0을 만들지 않는다 — 결측 문법)."""
    present = [v for v in values if v is not None]
    return round(sum(present), 2) if present else None


def _collect_overseas_cash(token: str, app_key: str, app_secret: str,
                           cano: str, prdt: str) -> dict:
    """위탁 계좌의 **외화예수금**(+기준환율) — CTRP6504R output2(통화별).

    실패해도 잔고 수집 전체를 무너뜨리지 않는다(빈 dict → 예수금만 결측).

    output3(계좌 합계)의 `tot_asst_amt`는 쓰지 않는다 — 실측에서 (주식+외화예수금)×환율의
    1.53배가 나왔다. 이 위탁 계좌 범위 밖의 자산까지 포함하는 값으로 보이며, 그대로 총액으로
    쓰면 없는 돈을 만들어낸다. 대신 검증된 두 값(주식평가액·외화예수금)을 직접 더한다.
    """
    try:
        import requests

        r = requests.get(_OVERSEAS_PRESENT_URL,
                         headers=_headers(token, _OVERSEAS_PRESENT_TR_ID, app_key, app_secret),
                         params={
                             "CANO": cano, "ACNT_PRDT_CD": prdt,
                             "WCRC_FRCR_DVSN_CD": "02",  # 02=외화 기준
                             "NATN_CD": "000",           # 000=전체 국가
                             "TR_MKET_CD": "00",         # 00=전체 시장
                             "INQR_DVSN_CD": "00",       # 00=전체
                         }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("rt_cd") != "0":
            log.warning("KIS 해외 예수금 조회 실패: %s", body.get("msg1"))
            return {}
        rows = body.get("output2") or []
        usd_row = next((x for x in rows if x.get("crcy_cd") == "USD"), None) or _first_row(rows)
        deposit = _pick_float(usd_row, "frcr_dncl_amt_2", "frcr_dncl_amt")
        log.info("KIS 위탁 외화예수금 확보: %s", deposit is not None)
        return {"deposit_usd": deposit, "fx_rate": _pick_float(usd_row, "frst_bltn_exrt")}
    except Exception as exc:  # noqa: BLE001
        log.warning("KIS 해외 예수금 수집 실패: %s", exc)
        return {}


def collect_isa_balance() -> dict | None:
    """ISA(ETF) 잔고 — {"holdings": [...], "summary": {...}} | None(미설정·실패).

    ISA 전용 앱키(KIS_ISA_APP_KEY)를 쓴다 — 위탁 앱키로는 이 계좌를 조회할 수 없다(실측)."""
    app_key, app_secret = _isa_credentials()
    token = _get_token(app_key, app_secret)
    if not token or not KIS_ACCOUNT_ISA:
        return None
    try:
        import requests

        cano, prdt = _split_account(KIS_ACCOUNT_ISA)
        r = requests.get(_DOMESTIC_BALANCE_URL,
                         headers=_headers(token, _DOMESTIC_TR_ID, app_key, app_secret), params={
            "CANO": cano, "ACNT_PRDT_CD": prdt,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        if body.get("rt_cd") != "0":
            log.warning("KIS ISA잔고 조회 실패: %s", body.get("msg1"))
            return None
        summary = _first_row(body.get("output2"))
        # 필드명은 KIS 공식 문서 기준(미검증) — tot_evlu_amt(총평가금액), evlu_pfls_smtl_amt(평가손익합계),
        # dnca_tot_amt(예수금총금액), prvs_rcdl_excc_amt(가수도정산금액 = D+2 예수금),
        # pchs_amt_smtl_amt(매입금액합계 = 투입원금).
        # 실측(2026-07-26) 관계식 확인: tot_evlu_amt == evlu_amt_smtl_amt + dnca_tot_amt.
        # 즉 **총평가금액은 예수금을 포함**한다(== nass_amt 순자산). 총자산 집계에는 이게 맞지만,
        # 화면에서 '평가액'과 '예수금'을 나란히 보여줄 때 더해서 읽히면 안 되므로 그 사실을
        # deposit_in_balance로 명시해 내보낸다. securities_krw는 예수금을 뺀 순수 유가증권 평가액.
        return {
            "holdings": body.get("output1", []),
            "summary": summary,
            "krw_value": _to_float(summary.get("tot_evlu_amt")),
            "securities_krw": _pick_float(summary, "evlu_amt_smtl_amt", "scts_evlu_amt"),
            "deposit_in_balance": True,
            "eval_pnl_krw": _to_float(summary.get("evlu_pfls_smtl_amt")),
            "principal_krw": _pick_float(summary, "pchs_amt_smtl_amt", "pchs_amt_smtl"),
            "deposit_krw": _pick_float(summary, "prvs_rcdl_excc_amt", "dnca_tot_amt"),
            "orderable_krw": _pick_float(summary, "nxdy_excc_amt", "dnca_tot_amt"),
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


def _pick_float(row: dict, *candidates: str) -> float | None:
    """응답 필드명이 미검증이라 후보를 순서대로 시도한다(첫 유효값 채택, 없으면 None=결측)."""
    for key in candidates:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None
