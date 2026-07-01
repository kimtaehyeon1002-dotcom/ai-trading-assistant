"""실시간 체결 구독 — 체결이 발생하면 콜백으로 저장 트리거. (KOA: OnReceiveChejanData)

체결 통보(gubun='0')를 받아 완료 주문을 매매일지로 넘길 수 있다. 실제 필드 파싱은
KOA Studio 기준으로 orders.parse_* 를 재사용한다.
"""
from __future__ import annotations

from collections.abc import Callable

from core.logging import get_logger
from services.kiwoom.api import KiwoomAPI

log = get_logger("kiwoom.realtime")


def subscribe_fills(api: KiwoomAPI, on_fill: Callable[[dict], None]) -> None:
    """체결/잔고 실시간 통보 등록. on_fill은 체결 dict를 받는다."""

    def _handler(gubun, item_cnt, fid_list):  # OnReceiveChejanData
        if gubun != "0":  # 0=주문체결, 1=잔고
            return
        try:
            fill = {
                "ticker": api.ocx.dynamicCall("GetChejanData(int)", 9001).strip().lstrip("A"),
                "name": api.ocx.dynamicCall("GetChejanData(int)", 302).strip(),
                "order_status": api.ocx.dynamicCall("GetChejanData(int)", 913).strip(),
                "filled_qty": api.ocx.dynamicCall("GetChejanData(int)", 911).strip(),
                "filled_price": api.ocx.dynamicCall("GetChejanData(int)", 910).strip(),
            }
            on_fill(fill)
        except Exception as exc:  # noqa: BLE001
            log.warning("체결 파싱 실패: %s", exc)

    api.ocx.OnReceiveChejanData.connect(_handler)
    log.info("실시간 체결 구독 등록")
