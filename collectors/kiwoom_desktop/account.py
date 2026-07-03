"""계좌 정보 — 계좌목록/예수금. (KOA: opw00001 등)"""
from __future__ import annotations

from utils.logging import get_logger
from collectors.kiwoom_desktop.api import KiwoomAPI

log = get_logger("kiwoom.account")


def list_accounts(api: KiwoomAPI) -> list[str]:
    raw = api.login_info("ACCNO")  # 계좌들이 ';'로 구분
    return [a for a in raw.split(";") if a]


def deposit(api: KiwoomAPI, account: str, pw: str = "") -> str:
    """예수금상세현황요청(opw00001). 반환은 문자열(원)."""
    api.set_input("계좌번호", account)
    api.set_input("비밀번호", pw)
    api.set_input("비밀번호입력매체구분", "00")
    api.set_input("조회구분", "2")
    meta = api.comm_rq("opw00001_req", "opw00001")
    return api.get_comm_data(meta.get("tr_code", "opw00001"), "opw00001_req", 0, "예수금")
