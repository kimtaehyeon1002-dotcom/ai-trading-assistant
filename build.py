"""정적 사이트 빌드 — 조립 루트(composition root). CLI와 데스크톱(app/main.py)이 공유.

  python build.py morning | news | trades | v2preview | dashboard | all

의존 방향: collectors → validators → repositories → calculators → generators (역방향 금지).
대시보드·AI Office·정적 자산은 매 빌드 갱신. 타깃 디스패치는 generators/registry.py(design/22 §6)를
순회하며, "all"의 범위는 레지스트리의 in_all=True 집합으로 정의한다(회귀 0 — design/20 Phase 1 DoD).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from collectors import notion_collector
from config.settings import ensure_dirs
from generators import registry
from generators.base import copy_static
from utils import runlog
from utils.logging import get_logger

log = get_logger("build")

TARGETS = (*registry.TARGETS.keys(), "dashboard", "all")


def _sync_notion() -> None:
    """Notion ERP 동기화 — 토큰 미설정이면 사실대로 skipped 기록(가짜 데이터 금지)."""
    if not notion_collector.enabled():
        runlog.note("Notion Sync", status="skipped", detail="NOTION_API_KEY/DB 미설정")
        return

    def _collect_and_persist():
        from repositories import notion_repository

        raw = notion_collector.collect()
        return notion_repository.save_normalized(raw) if raw else None

    runlog.run_step("Notion Sync", _collect_and_persist, fallback=None)


def run_build(target: str) -> list[Path]:
    """target 페이지 생성 + 공통 마무리(대시보드/정적 자산/AI Office). 반환=생성 경로들.

    레지스트리 타깃 중 일부(예: morning — design/20 Phase 5 정리점 결정)는 페이지를 쓰지 않고
    None을 반환할 수 있다 — 데이터 파이프라인은 실행되지만 발행물은 없다는 뜻이다. 반환 리스트·
    로그에는 실제로 쓰여진 페이지만 정직하게 남긴다(가짜 카운트 금지).
    """
    if target not in TARGETS:
        raise ValueError(f"알 수 없는 target: {target} (choices: {TARGETS})")

    ensure_dirs()
    _sync_notion()

    from generators.ai_office.generate import generate as gen_office
    # design/20 Phase 4: Dashboard가 v2로 치환됐다. v1 생성기(generators/dashboard)·템플릿
    # (dashboard.html)은 Phase 9 v1 셸 은퇴로 소스에서 제거됐다 — 필요 시 git 히스토리에서 복원한다.
    from generators.dashboard_v2.generate import generate as gen_dashboard

    pages: list[Path] = []
    if target == "all":
        for name in registry.ALL_TARGETS:
            result = registry.TARGETS[name].generate()
            if result is not None:
                pages.append(result)
    elif target in registry.TARGETS:
        result = registry.TARGETS[target].generate()
        if result is not None:
            pages.append(result)
    # target == "dashboard"는 별도 페이지 없이 공통 마무리만 수행(레지스트리 대상 아님, 기존 동작 보존)

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
