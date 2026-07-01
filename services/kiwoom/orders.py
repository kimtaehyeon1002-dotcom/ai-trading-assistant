"""실현손익(완료 매매) 조회 → Trade 변환 → 매매일지 적재.

KOA: opt10074(일자별실현손익상세) 등. 필드명은 KOA Studio 기준이며 계좌/환경에 맞게 조정 필요.
보유일수가 TR에 없으면 매입일/매도일로 계산하거나 0(당일)으로 둔다.
"""
from __future__ import annotations

from core.logging import get_logger
from models.trade import Trade
from services import journal
from services.kiwoom.api import KiwoomAPI

log = get_logger("kiwoom.orders")


def _num(s: str) -> float:
    try:
        return float(str(s).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def fetch_realized(api: KiwoomAPI, account: str, start_date: str) -> list[Trade]:
    """일자별 실현손익(opt10074) → Trade 목록. start_date=YYYYMMDD."""
    api.set_input("계좌번호", account)
    api.set_input("시작일자", start_date)
    meta = api.comm_rq("opt10074_req", "opt10074")
    tr, rq = meta.get("tr_code", "opt10074"), "opt10074_req"
    trades: list[Trade] = []
    for i in range(meta.get("count", 0)):
        date = api.get_comm_data(tr, rq, i, "일자").replace("-", "")
        ymd = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date
        trades.append(
            Trade(
                date=ymd,
                ticker=api.get_comm_data(tr, rq, i, "종목코드").lstrip("A"),
                name=api.get_comm_data(tr, rq, i, "종목명"),
                buy_price=_num(api.get_comm_data(tr, rq, i, "매입단가")),
                sell_price=_num(api.get_comm_data(tr, rq, i, "체결단가")),
                quantity=_num(api.get_comm_data(tr, rq, i, "수량")),
                holding_days=int(_num(api.get_comm_data(tr, rq, i, "보유일수"))),
                account_type="위탁",
            )
        )
    log.info("실현손익 %d건 조회", len(trades))
    return trades


def sync_to_journal(api: KiwoomAPI, account: str, start_date: str) -> int:
    """조회 → dedup 적재. 반환=신규 건수 이후 전체 건수."""
    trades = fetch_realized(api, account, start_date)
    all_trades = journal.add_trades(trades)
    return len(all_trades)
