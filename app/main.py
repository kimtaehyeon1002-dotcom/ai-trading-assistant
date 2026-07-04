"""PyQt5 데스크톱 — 정적 사이트 빌드 트리거 + Kiwoom 로그인/동기화 + docs 열기.

Windows(32-bit + KOA)에서 실행. Kiwoom은 선택적: 미설치 환경에서도 빌드/미리보기는 동작한다.
    python -m app.main
"""
from __future__ import annotations

import webbrowser

from config.settings import DOCS_DIR
from utils.dates import now_kst
from utils.logging import get_logger

log = get_logger("app")


def _run_build(target: str) -> str:
    from build import run_build

    run_build(target)
    return f"{target} 빌드 완료 ({now_kst():%H:%M:%S})"


def _deploy() -> str:
    from app.deploy import commit_and_push

    try:
        pushed = commit_and_push(f"chore(desktop): sync {now_kst():%Y-%m-%d %H:%M}")
    except Exception as exc:  # noqa: BLE001 - git 미설정/원격 거부 등은 메시지로 안내
        return f"배포 실패: {exc}"
    return "커밋+푸시 완료" if pushed else "변경 없음 — 커밋 생략"


def _kiwoom_sync(start_date: str) -> str:
    from collectors.kiwoom_desktop import orders
    from collectors.kiwoom_desktop.account import list_accounts
    from collectors.kiwoom_desktop.api import KiwoomAPI, KiwoomError
    from repositories import trade_repository

    try:
        api = KiwoomAPI()
    except KiwoomError as exc:
        return f"Kiwoom 사용 불가: {exc}"
    if not api.connect():
        return "Kiwoom 로그인 실패"

    accounts = list_accounts(api)
    if not accounts:
        return "계좌를 찾을 수 없습니다"
    # 수집(raw) → 변환·병합은 repository 책임(계층 준수)
    all_trades = trade_repository.add_from_kiwoom(orders.fetch_realized(api, accounts[0], start_date))
    _run_build("trades")
    return f"동기화 완료 · 계좌 {accounts[0]} · 총 {len(all_trades)}건"


def main() -> int:
    try:
        from PyQt5.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLineEdit,
            QPlainTextEdit,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:  # noqa: BLE001
        print("PyQt5가 필요합니다(pip install PyQt5). CLI 빌드는 python build.py 사용.", exc)
        return 1

    app = QApplication([])
    win = QWidget()
    win.setWindowTitle("AI Trading Assistant")
    win.resize(560, 420)
    root = QVBoxLayout(win)

    log_view = QPlainTextEdit()
    log_view.setReadOnly(True)

    def out(msg: str) -> None:
        log_view.appendPlainText(msg)

    def make_btn(label: str, handler) -> QPushButton:
        b = QPushButton(label)
        b.clicked.connect(handler)
        return b

    row1 = QHBoxLayout()
    row1.addWidget(make_btn("모닝리포트 생성", lambda: out(_run_build("morning"))))
    row1.addWidget(make_btn("뉴스 갱신", lambda: out(_run_build("news"))))
    row1.addWidget(make_btn("매매일지 재생성", lambda: out(_run_build("trades"))))
    root.addLayout(row1)

    row2 = QHBoxLayout()
    start = QLineEdit("20260601")
    start.setPlaceholderText("조회 시작일 YYYYMMDD")
    row2.addWidget(start)
    row2.addWidget(make_btn("Kiwoom 로그인+동기화", lambda: out(_kiwoom_sync(start.text().strip()))))
    root.addLayout(row2)

    row3 = QHBoxLayout()
    row3.addWidget(make_btn("docs 열기(브라우저)", lambda: webbrowser.open((DOCS_DIR / "index.html").as_uri())))
    row3.addWidget(make_btn("커밋+푸시(배포)", lambda: out(_deploy())))
    root.addLayout(row3)
    root.addWidget(log_view)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
