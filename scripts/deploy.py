"""로컬에서 docs를 커밋/푸시(선택). GitHub Pages는 /docs 를 서빙하도록 설정.

CI에서는 workflow가 커밋/배포하므로 이 모듈은 데스크톱 수동 실행용이다.
"""
from __future__ import annotations

import subprocess

from config.settings import BASE_DIR
from utils.logging import get_logger

log = get_logger("github.deploy")


def commit_and_push(message: str, paths: tuple[str, ...] = ("docs", "data")) -> bool:
    """변경이 있으면 커밋+푸시. 반환=커밋 발생 여부."""
    subprocess.run(["git", "add", *paths], cwd=BASE_DIR, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
    if staged.returncode == 0:
        log.info("변경 없음 — 커밋 생략")
        return False
    subprocess.run(["git", "commit", "-m", message], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
    log.info("배포 커밋/푸시 완료")
    return True
