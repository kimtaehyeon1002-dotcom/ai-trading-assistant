"""정적 사이트 빌드 — 조립 루트(composition root). CLI와 데스크톱(app/main.py)이 공유.

  python build.py morning | news | trades | v2preview | dashboard | all

의존 방향: collectors → validators → repositories → calculators → generators (역방향 금지).
대시보드·AI Office·정적 자산은 매 빌드 갱신. 타깃 디스패치는 generators/registry.py(design/22 §6)를
순회하며, "all"의 범위는 레지스트리의 in_all=True 집합으로 정의한다(회귀 0 — design/20 Phase 1 DoD).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from collectors import obsidian_collector
from config.settings import ensure_dirs
from generators import registry
from generators.base import copy_static
from utils import runlog
from utils.logging import get_logger

log = get_logger("build")

TARGETS = (*registry.TARGETS.keys(), "dashboard", "all")


def _sync_vault() -> None:
    """Obsidian vault(워치리스트) 동기화 — 폴더 미존재/빈 폴더면 사실대로 skipped 기록."""
    if not obsidian_collector.enabled():
        runlog.note("Vault Sync", status="skipped", detail="TH_DATA/00_Watchlist 없음/비어있음")
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
    """target 페이지 생성 + 공통 마무리(대시보드/정적 자산/AI Office). 반환=생성 경로들.

    레지스트리 타깃 중 일부(예: morning — design/20 Phase 5 정리점 결정)는 페이지를 쓰지 않고
    None을 반환할 수 있다 — 데이터 파이프라인은 실행되지만 발행물은 없다는 뜻이다. 반환 리스트·
    로그에는 실제로 쓰여진 페이지만 정직하게 남긴다(가짜 카운트 금지).
    """
    if target not in TARGETS:
        raise ValueError(f"알 수 없는 target: {target} (choices: {TARGETS})")

    ensure_dirs()
    _sync_vault()

    from generators import vault_journal
    from generators.ai_office.generate import generate as gen_office
    # design/20 Phase 4: Dashboard가 v2로 치환됐다. v1 생성기(generators/dashboard)·템플릿
    # (dashboard.html)은 Phase 9 v1 셸 은퇴로 소스에서 제거됐다 — 필요 시 git 히스토리에서 복원한다.
    from generators.dashboard_v2.generate import generate as gen_dashboard

    pages: list[Path] = []
    # vault write-back(10_Journal/)은 해당 타깃 발행 직후 수행 — 레지스트리 순회와 결합한다.
    vault_writers = {
        "morning": vault_journal.write_morning,
        "news": vault_journal.write_news,
        "trades": vault_journal.write_trades,
    }
    if target == "all":
        names: tuple[str, ...] = registry.ALL_TARGETS
    elif target in registry.TARGETS:
        names = (target,)
    else:
        # target == "dashboard"는 별도 페이지 없이 공통 마무리만 수행(레지스트리 대상 아님, 기존 동작 보존)
        names = ()

    vault_notes = 0
    for name in names:
        result = registry.TARGETS[name].generate()
        if result is not None:
            pages.append(result)
        writer = vault_writers.get(name)
        if writer:
            vault_notes += _vault_write(writer)

    if vault_notes or vault_journal.enabled():
        runlog.note("Vault Journal", items=vault_notes, detail="10_Journal/ write-back")

    # 공통 마무리: 대시보드 + 정적 자산 + AI Office(실행 기록 발행) + 신선도 메타(runlog 파생)
    pages.append(gen_dashboard())
    copy_static()
    runlog.note("Publisher", items=len(pages) + 1, detail="pages + static")
    pages.append(gen_office())

    from generators.freshness_meta import generate as gen_freshness_meta
    gen_freshness_meta()  # runlog.json 발행 이후에 호출해야 정확하다(병합된 워커 기록을 읽음)

    from repositories import search_repository
    from repositories.news_repository import load_store
    search_repository.persist(search_repository.build(load_store()))

    log.info("빌드 완료: %s (%d pages)", target, len(pages))
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Trading Assistant 정적 사이트 빌드")
    ap.add_argument("target", choices=TARGETS)
    run_build(ap.parse_args().target)


if __name__ == "__main__":
    main()
