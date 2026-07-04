"""계좌 정보 — 계좌목록."""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.logging import get_logger

log = get_logger("kiwoom.account")


def list_accounts(api: KiwoomAPI) -> list[str]:
    raw = api.login_info("ACCNO")  # 계좌들이 ';'로 구분
    accounts = [a for a in raw.split(";") if a]
    log.info("계좌 목록: %s", accounts)
    return accounts
