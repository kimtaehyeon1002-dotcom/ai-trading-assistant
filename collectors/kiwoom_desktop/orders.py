"""실현손익(완료 매매) TR 조회 — raw dict 반환(모델 변환은 repositories/trade_repository).

KOA: opt10074(일자별실현손익상세). 필드명은 KOA Studio 기준, 실계좌에서 조정 필요.
"""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.logging import get_logger

log = get_logger("collectors.kiwoom_orders")


def fetch_realized(api: KiwoomAPI, account: str, start_date: str) -> list[dict]:
    """일자별 실현손익 raw rows. start_date=YYYYMMDD."""
    api.set_input("계좌번호", account)
    api.set_input("시작일자", start_date)
    meta = api.comm_rq("opt10074_req", "opt10074")
    tr, rq = meta.get("tr_code", "opt10074"), "opt10074_req"
    rows: list[dict] = []
    for i in range(meta.get("count", 0)):
        rows.append(
            {
                "일자": api.get_comm_data(tr, rq, i, "일자"),
                "종목코드": api.get_comm_data(tr, rq, i, "종목코드"),
                "종목명": api.get_comm_data(tr, rq, i, "종목명"),
                "매입단가": api.get_comm_data(tr, rq, i, "매입단가"),
                "체결단가": api.get_comm_data(tr, rq, i, "체결단가"),
                "수량": api.get_comm_data(tr, rq, i, "수량"),
                "보유일수": api.get_comm_data(tr, rq, i, "보유일수"),
            }
        )
    log.info("실현손익 %d건 조회", len(rows))
    return rows
