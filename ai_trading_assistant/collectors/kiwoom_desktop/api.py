"""Kiwoom OpenAPI+ 저수준 래퍼(QAxWidget) — 로그인/TR 요청/데이터 조회.

PyQt5 QAxContainer는 Windows에서만 제공(Kiwoom OCX가 32-bit 전용이라 PySide6는 32-bit wheel이
없어 사용 불가). 미가용 시 KiwoomError를 던져 상위에서 안내.
TR 필드명은 KOA Studio 기준이며, 실제 값 파싱은 orders/account에서 수행한다.
"""
from __future__ import annotations

from utils.logging import get_logger

log = get_logger("kiwoom.api")

CONTROL = "KHOPENAPI.KHOpenAPICtrl.1"


def fix_mojibake(s: str) -> str:
    """OCX가 EUC-KR 문자열을 latin-1로 잘못 디코딩해 주는 경우 복원.

    예: '¸®³ë°ø¾÷' → '리노공업'. 순수 ASCII(숫자/코드)는 그대로 통과.
    """
    if not s or all(ord(c) < 128 for c in s):
        return s
    try:
        fixed = s.encode("latin-1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s
    # 복원 결과에 한글이 있어야 진짜 mojibake였던 것
    return fixed if any("가" <= c <= "힣" for c in fixed) else s


class KiwoomError(RuntimeError):
    pass


class KiwoomAPI:
    def __init__(self) -> None:
        try:
            from PyQt5.QAxContainer import QAxWidget
            from PyQt5.QtCore import QEventLoop
        except Exception as exc:  # noqa: BLE001
            raise KiwoomError(
                "Kiwoom OpenAPI+는 Windows 32-bit Python + PyQt5(QAxContainer) + KOA 설치가 필요합니다: "
                f"{exc}"
            ) from exc

        self._QEventLoop = QEventLoop
        self.ocx = QAxWidget(CONTROL)
        self.connected = False
        self._login_loop = None
        self._tr_loop = None
        self._tr_meta: dict = {}
        self._tr_fields: list[str] = []
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr)
        self.ocx.OnReceiveMsg.connect(self._on_receive_msg)

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

    def comm_rq(
        self,
        rq_name: str,
        tr_code: str,
        prev_next: int = 0,
        screen: str = "0101",
        fields: list[str] | None = None,
    ) -> dict:
        """TR 요청. fields를 주면 각 행을 OnReceiveTrData '안에서' 읽어 meta['rows']로 반환.

        (TR 데이터 버퍼는 콜백 종료 후 무효화되므로 밖에서 GetCommData하면 빈 값이 온다.)
        """
        self._tr_fields = list(fields or [])
        self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)", rq_name, tr_code, prev_next, screen
        )
        self._tr_loop = self._QEventLoop()
        self._tr_loop.exec()
        return self._tr_meta.get(rq_name, {})

    def _on_receive_msg(self, screen, rq_name, tr_code, msg) -> None:
        """서버 메시지(입력값 오류·조회 결과 등) — 0건 원인 파악에 필수."""
        log.info("서버 메시지 [%s/%s] %s", rq_name, tr_code, fix_mojibake(str(msg)))

    def _on_receive_tr(self, screen, rq_name, tr_code, record, prev_next, *args) -> None:
        count = int(self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, rq_name) or 0)
        rows: list[dict] = []
        # 단일 레코드 TR(시세 등)은 반복행이 0 — index 0으로 한 행은 읽는다
        for i in range(max(count, 1) if self._tr_fields else 0):
            rows.append({f: self.get_comm_data(tr_code, rq_name, i, f) for f in self._tr_fields})
        if count == 0 and rows and not any(rows[0].values()):
            rows = []  # 다중행 TR의 0건 응답 — 유령 빈 행 제거
        self._tr_meta[rq_name] = {
            "tr_code": tr_code,
            "count": count,
            "prev_next": prev_next,
            "rows": rows,
        }
        if self._tr_loop:
            self._tr_loop.quit()

    def get_comm_data(self, tr_code: str, rq_name: str, index: int, field: str) -> str:
        raw = (
            self.ocx.dynamicCall(
                "GetCommData(QString, QString, int, QString)", tr_code, rq_name, index, field
            )
            or ""
        ).strip()
        return fix_mojibake(raw)
