"""계좌 정보 — 계좌목록·잔고(design/20 Phase 8).

fetch_balance()는 2026-07-27 실계좌(Windows 32-bit + HTS 로그인)로 검증 완료. 최초 시도 시
입력필드에 없는 "상장폐지조회구분"을 잘못 넣어 [400721] 조회구분을 확인하세요 오류가 났다 —
실제 opw00018 필수 입력은 계좌번호/비밀번호/비밀번호입력매체구분/조회구분(1=합산,2=개별)이며
개별 종목 행이 필요해 "2"로 고정했다. summary/holding 필드명 후보는 실응답으로 확인됨(4계좌
전량 확보 로그 참고).

예수금은 **TR이 다르다**(2026-08-03): opw00018은 유가증권 평가 계열만 돌려주고 예수금은
opw00001(예수금상세현황요청) 소관이다. 잔고 TR에만 "예수금" 후보를 걸어둔 동안 키움만
예수금이 영구 결측이었다(다른 3계좌는 REST 응답에 포함돼 정상 표시됐다).
⚠ opw00001의 입력 조회구분 값과 출력 필드명은 **아직 실계좌로 검증되지 않았다** — 후보
목록으로 흡수해 두었고, 결측이면 `예수금 raw(필드 진단용)` 로그의 실제 키를 보고 고친다.
"""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.logging import get_logger

log = get_logger("kiwoom.account")

_BALANCE_TR_CODE = "opw00018"  # 계좌평가잔고내역요청(KOA 문서 기준, 미검증)
_BALANCE_RQ_NAME = "opw00018_req"

# 예수금은 **잔고 TR이 주지 않는다** — opw00018은 유가증권 평가 계열만 돌려주고, 예수금은
# opw00001(예수금상세현황요청) 소관이다. 이걸 몰라 opw00018에만 "예수금" 후보를 걸어둔 동안
# 키움만 예수금이 영구 결측이었다(다른 3계좌는 REST 응답에 포함돼 정상 표시).
_DEPOSIT_TR_CODE = "opw00001"
_DEPOSIT_RQ_NAME = "opw00001_req"

_SUMMARY_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    # opw00018에 있으면 그걸 쓰고, 없으면 아래 opw00001 결과로 채운다(둘 다 후보 유지).
    "예수금": ("예수금", "예수금액"),
    "주문가능금액": ("주문가능금액", "d+2추정예수금", "D+2추정예수금"),
    "총평가금액": ("총평가금액",),
    "총매입금액": ("총매입금액",),
    "총평가손익금액": ("총평가손익금액",),
    "총수익률": ("총수익률(%)", "총수익률"),
}
# opw00001 출력 필드명은 KOA 표기 흔들림(대소문자·d+2 등)이 있어 후보로 흡수한다.
_DEPOSIT_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "예수금": ("예수금", "예수금액"),
    # 주문가능금액이 없으면 D+2 추정예수금이 실질적인 주문 가능액이다.
    "주문가능금액": ("주문가능금액", "출금가능금액",
                     "d+2추정예수금", "D+2추정예수금", "d+2추정예수금", "D+2추정예수금액"),
}
# 매입가·현재가·수익률은 design/09 보유종목 테이블(매입단가/현재가/수익률 열)의 필수 재료다 —
# 초기 구현이 평가금액·평가손익만 읽어서 그 열들을 그릴 수 없었다. KOA opw00018 필드명은
# 미검증이라 표기 흔들림(매입가/매입단가 등)을 후보 목록으로 흡수한다.
_HOLDING_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "종목코드": ("종목번호", "종목코드"),
    "종목명": ("종목명",),
    "보유수량": ("보유수량",),
    "매입가": ("매입가", "매입단가"),
    "현재가": ("현재가",),
    "평가금액": ("평가금액",),
    "평가손익": ("평가손익",),
    "수익률": ("수익률(%)", "수익률"),
}


def list_accounts(api: KiwoomAPI) -> list[str]:
    raw = api.login_info("ACCNO")  # 계좌들이 ';'로 구분
    accounts = [a for a in raw.split(";") if a]
    log.info("계좌 목록: %s", accounts)
    return accounts


def _pick(row: dict, candidates: tuple[str, ...]) -> str:
    for f in candidates:
        if row.get(f):
            return row[f]
    return ""


def fetch_deposit(api: KiwoomAPI, account: str) -> dict:
    """예수금상세현황(opw00001) — {"예수금": str, "주문가능금액": str}. 실패 시 빈 값.

    잔고(opw00018)와 별개 TR이라 따로 호출한다. 실패해도 잔고 수집을 막지 않는다 —
    예수금만 결측으로 남고 나머지 계좌 정보는 그대로 표시된다(결측 문법).
    """
    try:
        # 조회구분 2=일반조회(3=추정조회). 예수금 실잔고가 필요하므로 일반조회를 쓴다.
        api.set_input("계좌번호", account)
        api.set_input("비밀번호", "")
        api.set_input("비밀번호입력매체구분", "00")
        api.set_input("조회구분", "2")
        meta = api.comm_rq(_DEPOSIT_RQ_NAME, _DEPOSIT_TR_CODE,
                           fields=[f for c in _DEPOSIT_FIELD_CANDIDATES.values() for f in c])
    except Exception as exc:  # noqa: BLE001
        log.warning("Kiwoom 예수금 조회 실패(잔고는 계속): %s", exc)
        return {}
    row = (meta.get("rows") or [{}])[0]
    out = {key: _pick(row, cands) for key, cands in _DEPOSIT_FIELD_CANDIDATES.items()}
    # 필드명이 미검증이라 raw를 남긴다 — 결측이면 이 로그로 실제 키를 확인해 후보를 고친다.
    log.info("예수금 raw(필드 진단용): %s", row)
    return out


def fetch_balance(api: KiwoomAPI, account: str) -> dict | None:
    """계좌 잔고 — {"summary": {...}, "holdings": [...]} | None(조회 실패).

    summary/holdings의 값은 전부 원시 문자열(콤마 포함 가능) — 숫자 변환·검증은
    validators/asset_validator.py 몫이다(수집기는 원장 그대로만 옮긴다).
    """
    try:
        api.set_input("계좌번호", account)
        api.set_input("비밀번호", "")
        api.set_input("비밀번호입력매체구분", "00")
        api.set_input("조회구분", "2")  # 1=합산, 2=개별(보유종목별 행 필요 → design/09 테이블)
        meta = api.comm_rq(_BALANCE_RQ_NAME, _BALANCE_TR_CODE,
                            fields=[f for c in {**_SUMMARY_FIELD_CANDIDATES, **_HOLDING_FIELD_CANDIDATES}.values() for f in c])
    except Exception as exc:  # noqa: BLE001
        log.warning("Kiwoom 잔고 조회 실패: %s", exc)
        return None
    # opw00018의 예수금·총평가금액 등은 "단일값" 필드이지만, 이 프로젝트의 범용 comm_rq
    # 래퍼는 반복행(GetRepeatCnt) 인덱스 루프 하나로 모든 필드를 읽는다(api.py 참조) — 단일값
    # 필드는 KOA에서 인덱스 무관하게 동일 값을 반환하는 것이 일반적이므로 rows[0]에서 취한다.
    summary_raw = (meta.get("rows") or [{}])[0]
    summary = {key: _pick(summary_raw, cands) for key, cands in _SUMMARY_FIELD_CANDIDATES.items()}
    holdings = [
        {key: _pick(raw, cands) for key, cands in _HOLDING_FIELD_CANDIDATES.items()}
        for raw in meta.get("rows", [])
    ]
    # 잔고 TR이 비워둔 예수금 계열만 별도 TR로 채운다(있으면 덮지 않는다).
    if not summary.get("예수금") or not summary.get("주문가능금액"):
        for key, value in fetch_deposit(api, account).items():
            if value and not summary.get(key):
                summary[key] = value
    # 요약 원시값을 남긴다 — 필드명·스케일 문제를 로그 없이 추적할 수 없었다(총수익률이
    # 100배 스케일로 와서 화면에 -1718%가 뜬 사고, design/25 §8-2). 시세·주문 수집기는
    # 이미 같은 형태의 raw 로그를 남기고 있고 그게 과거 버그를 잡은 방법이었다.
    log.info("잔고 summary raw(필드 진단용): %s | 보유 %d종목", summary, len(holdings))
    return {"summary": summary, "holdings": holdings}
