"""헤드리스 Kiwoom 동기화 — 로그인→체결수집→원장병합→빌드→(옵션)배포.

GUI 창을 띄우지 않아 AMD 오버레이(AMDXN32.DLL) 주입 대상이 되지 않고, 작업 완료 후
os._exit(0)로 Qt/DLL 종료 시퀀스를 통째로 건너뛴다 — 종료 중 stale hook가 호출되며 나던
0xc0000005 크래시를 회피하는 것이 목적이다. OCX 호스팅에 QApplication 인스턴스는 필요하지만
창(show)은 만들지 않는다(로그인/TR 콜백은 api.py의 중첩 QEventLoop가 처리).

    python -m app.sync [시작일 YYYYMMDD] [--push]
"""
from __future__ import annotations

import os
import sys

from utils.logging import get_logger

log = get_logger("app.sync")

DEFAULT_START = "20260601"


def run(start_date: str, push: bool) -> None:
    from PyQt5.QtWidgets import QApplication

    qt_app = QApplication([])  # OCX 호스팅용 — 창은 만들지 않는다
    _ = qt_app  # 참조 유지 필수: 변수에 안 담으면 GC로 파괴되어 QWidget 생성이 즉사한다

    from build import run_build
    from collectors.kiwoom_desktop import orders
    from collectors.kiwoom_desktop.account import list_accounts
    from collectors.kiwoom_desktop.api import KiwoomAPI, KiwoomError
    from repositories import trade_repository

    try:
        api = KiwoomAPI()
    except KiwoomError as exc:
        log.error("Kiwoom 사용 불가: %s", exc)
        return
    if not api.connect():
        log.error("Kiwoom 로그인 실패")
        return
    accounts = list_accounts(api)
    if not accounts:
        log.error("계좌를 찾을 수 없습니다")
        return

    all_trades = trade_repository.add_from_kiwoom(
        orders.fetch_realized(api, accounts[0], start_date)
    )

    # 야간선물(모닝리포트용) — 실패해도 매매 동기화는 막지 않는다
    try:
        from collectors import kiwoom_collector
        from collectors.kiwoom_desktop import futures

        night = futures.fetch_night_futures(api)
        if night.get("kospi_night") or night.get("kosdaq_night"):
            kiwoom_collector.save_night_futures(
                kospi=night.get("kospi_night"), kosdaq=night.get("kosdaq_night")
            )
            log.info("야간선물 저장: %s", night)
        else:
            log.warning("야간선물 시세 없음(종목 미발견/휴장) — 캐시 미갱신")
    except Exception as exc:  # noqa: BLE001
        log.warning("야간선물 조회 실패(무시하고 계속): %s", exc)

    run_build("trades")
    log.info("동기화 완료 · 계좌 %s · 총 %d건", accounts[0], len(all_trades))

    if push:
        from app.deploy import commit_and_push
        from utils.dates import now_kst

        try:
            pushed = commit_and_push(f"chore(desktop): sync {now_kst():%Y-%m-%d %H:%M}")
            log.info("배포: %s", "커밋+푸시 완료" if pushed else "변경 없음")
        except Exception as exc:  # noqa: BLE001 - git 미설정/원격 거부는 로그로만
            log.error("배포 실패: %s", exc)


def main() -> None:
    args = sys.argv[1:]
    push = "--push" in args
    dates = [a for a in args if a.isdigit() and len(a) == 8]
    run(dates[0] if dates else DEFAULT_START, push)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # Qt/DLL 종료 시퀀스 skip → AMD stale hook 크래시 회피


if __name__ == "__main__":
    main()
