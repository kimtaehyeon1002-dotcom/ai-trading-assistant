"""Kiwoom OpenAPI+ 저수준 래퍼(QAxWidget) — 로그인/TR 요청/데이터 조회.

PySide6 QtAxContainer는 Windows에서만 제공. 미가용 시 KiwoomError를 던져 상위에서 안내.
TR 필드명은 KOA Studio 기준이며, 실제 값 파싱은 orders/account에서 수행한다.
"""
from __future__ import annotations

from utils.logging import get_logger

log = get_logger("kiwoom.api")

CONTROL = "KHOPENAPI.KHOpenAPICtrl.1"


class KiwoomError(RuntimeError):
    pass


class KiwoomAPI:
    def __init__(self) -> None:
        try:
            from PySide6.QtAxContainer import QAxWidget
            from PySide6.QtCore import QEventLoop
        except Exception as exc:  # noqa: BLE001
            raise KiwoomError(
                "Kiwoom OpenAPI+는 Windows 32-bit Python + PySide6(QtAxContainer) + KOA 설치가 필요합니다: "
                f"{exc}"
            ) from exc

        self._QEventLoop = QEventLoop
        self.ocx = QAxWidget(CONTROL)
        self.connected = False
        self._login_loop = None
        self._tr_loop = None
        self._tr_meta: dict = {}
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr)

    # ── 로그인 ──
    def connect(self) -> bool:
        self.ocx.dynamicCall("CommConnect()")
        self._login_loop = self._QEventLoop()
        self._login_loop.exec()
        return self.connected

    def _on_event_connect(self, err_code: int) -> None:
        self.connected = err_code == 0
        log.info("로그인 결과 err=%s", err_code)
        if self._login_loop:
            self._login_loop.quit()

    def login_info(self, tag: str) -> str:
        """ACCNO(계좌목록;구분), USER_ID, USER_NAME 등."""
        return self.ocx.dynamicCall("GetLoginInfo(QString)", tag)

    # ── TR ──
    def set_input(self, key: str, value: str) -> None:
        self.ocx.dynamicCall("SetInputValue(QString, QString)", key, value)

    def comm_rq(self, rq_name: str, tr_code: str, prev_next: int = 0, screen: str = "0101") -> dict:
        self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)", rq_name, tr_code, prev_next, screen
        )
        self._tr_loop = self._QEventLoop()
        self._tr_loop.exec()
        return self._tr_meta.get(rq_name, {})

    def _on_receive_tr(self, screen, rq_name, tr_code, record, prev_next, *args) -> None:
        count = int(self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name) or 0)
        self._tr_meta[rq_name] = {"tr_code": tr_code, "count": count, "prev_next": prev_next}
        if self._tr_loop:
            self._tr_loop.quit()

    def get_comm_data(self, tr_code: str, rq_name: str, index: int, field: str) -> str:
        return (
            self.ocx.dynamicCall(
                "GetCommData(QString, QString, int, QString)", tr_code, rq_name, index, field
            )
            or ""
        ).strip()

    # ── 실시간 ──
    def set_real_reg(self, screen: str, codes: str, fids: str, opt: str = "0") -> None:
        self.ocx.dynamicCall(
            "SetRealReg(QString, QString, QString, QString)", screen, codes, fids, opt
        )
