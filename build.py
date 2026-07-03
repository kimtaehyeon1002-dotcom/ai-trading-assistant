"""정적 사이트 빌드 CLI — 조립 루트(composition root).

  python build.py morning | news | trades | dashboard | all

의존 방향: collectors → validators → repositories → calculators → generators (역방향 금지).
대시보드·AI Office·정적 자산은 매 빌드 갱신.
"""
from __future__ import annotations

import argparse

from collectors import notion_collector
from config.settings import ensure_dirs
from generators.base import copy_static
from utils import runlog
from utils.logging import get_logger

log = get_logger("build")


def _sync_notion() -> None:
    """Notion ERP 동기화 — 토큰 미설정이면 사실대로 skipped 기록(가짜 데이터 금지)."""
    if not notion_collector.enabled():
        runlog.note("Notion Sync", status="skipped", detail="NOTION_API_KEY/DB 미설정")
        return
    runlog.run_step("Notion Sync", notion_collector.collect, fallback=None)


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Trading Assistant 정적 사이트 빌드")
    ap.add_argument("target", choices=["morning", "news", "trades", "dashboard", "all"])
    args = ap.parse_args()

    ensure_dirs()
    _sync_notion()

    from generators.ai_office.generate import generate as gen_office
    from generators.dashboard.generate import generate as gen_dashboard
    from generators.morning.generate import generate as gen_morning
    from generators.news.generate import generate as gen_news
    from generators.trades.generate import generate as gen_trades

    pages = []
    if args.target in ("morning", "all"):
        pages.append(gen_morning())
    if args.target in ("news", "all"):
        pages.append(gen_news())
    if args.target in ("trades", "all"):
        pages.append(gen_trades())

    # 공통 마무리: 대시보드 + 정적 자산 + AI Office(실행 기록 발행)
    pages.append(gen_dashboard())
    copy_static()
    runlog.note("Publisher", items=len(pages) + 1, detail="pages + static")
    pages.append(gen_office())

    log.info("빌드 완료: %s (%d pages)", args.target, len(pages))


if __name__ == "__main__":
    main()
