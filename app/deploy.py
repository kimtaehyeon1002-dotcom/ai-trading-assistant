"""로컬에서 docs/data를 커밋/푸시(선택). GitHub Pages는 /docs 를 서빙하도록 설정.

CI(뉴스 워크플로)가 30분마다 자동 푸시하므로, 데스크톱 수동 배포는 푸시 전에 원격 변경을
rebase로 흡수해야 한다(안 그러면 non-fast-forward로 거부됨). 생성물(docs) 충돌은 원격을
받아들인 뒤 data/trades.json(진실원)으로 재빌드해 해소한다.
"""
from __future__ import annotations

import subprocess

from config.settings import BASE_DIR
from utils.logging import get_logger

log = get_logger("app.deploy")


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=BASE_DIR, check=check)


def commit_and_push(message: str, paths: tuple[str, ...] = ("docs", "data")) -> bool:
    """변경이 있으면 커밋 → 원격 rebase 흡수 → 재빌드 → 푸시. 반환=커밋 발생 여부."""
    _git("add", *paths)
    if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
        log.info("변경 없음 — 커밋 생략")
        return False
    _git("commit", "-m", message)

    # 원격의 뉴스 자동커밋을 흡수(생성물 충돌은 원격 우선 → 아래서 재빌드로 정정).
    # --autostash: 커밋 대상(docs/data) 밖의 unstaged 변경이 있어도 rebase가 거부하지 않게
    # (개발 중 소스 수정이 워킹트리에 남아 있으면 이게 없을 때 배포가 통째로 실패한다)
    _git("fetch", "origin")
    rebased = _git("rebase", "--autostash", "-X", "theirs", "origin/main", check=False)
    if rebased.returncode != 0:
        _git("rebase", "--abort", check=False)
        log.error("원격 변경 흡수(rebase) 실패 — 수동 확인 필요")
        raise RuntimeError("rebase 충돌: git 상태를 직접 확인하세요")

    # data/trades.json(진실원)으로 매매일지·대시보드 재생성 후 정정 커밋
    from build import run_build

    run_build("trades")
    _git("add", *paths)
    if _git("diff", "--cached", "--quiet", check=False).returncode != 0:
        _git("commit", "-m", f"{message} (rebuild)")

    _git("push")
    log.info("배포 커밋/푸시 완료")
    return True


def main() -> None:
    from utils.dates import now_kst

    commit_and_push(f"chore(desktop): sync {now_kst():%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
