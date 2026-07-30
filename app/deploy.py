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


def _restore_remote_runlog() -> None:
    """rebase 후 runlog.json에 원격(CI)의 워커 기록을 되살린다.

    rebase는 `-X theirs`로 충돌 시 **데스크톱 사본**을 채택한다(생성물은 재빌드로 정정한다는
    전제). 그런데 runlog.json은 재빌드로 복원되지 않는 누적 원장이라, 데스크톱이 돌리지 않는
    워커(financials·stock·macro)의 기록이 통째로 사라진다.

    이 단계는 run_build 이전이어야 한다 — 직후의 ai_office.generate()가 이 파일을 prev로 읽어
    발행하기 때문이다. 실패해도 배포를 막지 않는다.

    구현은 scripts/merge_remote_runlog로 옮겼다 — CI의 commit-push 액션도 같은 병합이
    필요해졌고(방향만 반대인 같은 유실), 두 벌로 두면 반드시 어긋난다.
    """
    from scripts.merge_remote_runlog import merge_from_ref

    try:
        restored = merge_from_ref("origin/main")
    except OSError as exc:  # noqa: BLE001 - 배포를 막지 않는다
        log.warning("runlog 원격 병합 실패(배포는 계속): %s", exc)
        return
    if restored > 0:
        log.info("runlog: 원격 워커 기록 %d종 복원", restored)


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

    _restore_remote_runlog()

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
