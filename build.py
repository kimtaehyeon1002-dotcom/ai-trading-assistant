"""정적 사이트 빌드 — 조립 루트(composition root). CLI와 데스크톱(app/main.py)이 공유.

  python build.py morning | news | trades | dashboard | all

의존 방향: collectors → validators → repositories → calculators → generators (역방향 금지).
대시보드·AI Office·정적 자산은 매 빌드 갱신.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from collectors import obsidian_collector
from config.settings import ensure_dirs
from generators.base import copy_static
from utils import runlog
from utils.logging import get_logger

log = get_logger("build")

TARGETS = ("morning", "news", "trades", "dashboard", "all")


def _sync_vault() -> None:
    """Obsidian vault(워치리스트) 동기화 — 폴더 미존재/빈 폴더면 사실대로 skipped 기록."""
    if not obsidian_collector.enabled():
        runlog.note("Vault Sync", status="skipped", detail="vault/00_Watchlist 없음/비어있음")
        return

    def _collect_and_persist():
        from repositories import obsidian_repository

        raw = obsidian_collector.collect()
        return obsidian_repository.save_normalized(raw) if raw else None

    runlog.run_step("Vault Sync", _collect_and_persist, fallback=None)


def _vault_write(fn) -> int:
    """vault_journal 쓰기 함수 1개 실행 → 기록된 노트 개수(부분 실패 허용, 사실대로 로그)."""
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - 저널 write-back 실패가 빌드 전체를 막지 않음
        log.warning("vault_journal.%s 실패: %s", fn.__name__, exc)
        return 0
    if result is None:
        return 0
    if isinstance(result, list):
        return len(result)
    return 1


def run_build(target: str) -> list[Path]:
    """target 페이지 생성 + 공통 마무리(대시보드/정적 자산/AI Office). 반환=생성 경로들."""
    if target not in TARGETS:
        raise ValueError(f"알 수 없는 target: {target} (choices: {TARGETS})")

    ensure_dirs()
    _sync_vault()

    from generators import vault_journal
    from generators.ai_office.generate import generate as gen_office
    from generators.dashboard.generate import generate as gen_dashboard
    from generators.morning.generate import generate as gen_morning
    from generators.news.generate import generate as gen_news
    from generators.trades.generate import generate as gen_trades

    pages: list[Path] = []
    vault_notes = 0
    if target in ("morning", "all"):
        pages.append(gen_morning())
        vault_notes += _vault_write(vault_journal.write_morning)
    if target in ("news", "all"):
        pages.append(gen_news())
        vault_notes += _vault_write(vault_journal.write_news)
    if target in ("trades", "all"):
        pages.append(gen_trades())
        vault_notes += _vault_write(vault_journal.write_trades)

    if vault_notes or vault_journal.enabled():
        runlog.note("Vault Journal", items=vault_notes, detail="10_Journal/ write-back")

    # 공통 마무리: 대시보드 + 정적 자산 + AI Office(실행 기록 발행)
    pages.append(gen_dashboard())
    copy_static()
    runlog.note("Publisher", items=len(pages) + 1, detail="pages + static")
    pages.append(gen_office())

    log.info("빌드 완료: %s (%d pages)", target, len(pages))
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Trading Assistant 정적 사이트 빌드")
    ap.add_argument("target", choices=TARGETS)
    run_build(ap.parse_args().target)


if __name__ == "__main__":
    main()
