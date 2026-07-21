"""계좌 정보 — 계좌목록·잔고(design/20 Phase 8).

⚠ fetch_balance()는 실제 Kiwoom OCX 세션(Windows 32-bit + HTS 로그인)으로 검증하지 못했다 —
이 개발 환경엔 그 실행 조건 자체가 없다(orders.py의 TR 패턴을 그대로 따랐을 뿐). 실계좌 연동
전 KOA Studio로 opw00018 응답 필드를 반드시 실측 확인해야 한다(다른 수집기의 "미검증" 고지와
같은 원칙이나, 이건 네트워크 키가 아니라 OCX 세션 자체가 없어 한 단계 더 불확실하다).
"""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.logging import get_logger

log = get_logger("kiwoom.account")

_BALANCE_TR_CODE = "opw00018"  # 계좌평가잔고내역요청(KOA 문서 기준, 미검증)
_BALANCE_RQ_NAME = "opw00018_req"

_SUMMARY_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "예수금": ("예수금",),
    "총평가금액": ("총평가금액",),
    "총매입금액": ("총매입금액",),
    "총평가손익금액": ("총평가손익금액",),
    "총수익률": ("총수익률(%)", "총수익률"),
}
_HOLDING_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "종목코드": ("종목코드",),
    "종목명": ("종목명",),
    "보유수량": ("보유수량",),
    "평가금액": ("평가금액",),
    "평가손익": ("평가손익",),
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


def fetch_balance(api: KiwoomAPI, account: str) -> dict | None:
    """계좌 잔고 — {"summary": {...}, "holdings": [...]} | None(조회 실패).

    summary/holdings의 값은 전부 원시 문자열(콤마 포함 가능) — 숫자 변환·검증은
    validators/asset_validator.py 몫이다(수집기는 원장 그대로만 옮긴다).
    """
    try:
        api.set_input("계좌번호", account)
        api.set_input("비밀번호", "")
        api.set_input("상장폐지조회구분", "0")
        api.set_input("비밀번호입력매체구분", "00")
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
    return {"summary": summary, "holdings": holdings}
