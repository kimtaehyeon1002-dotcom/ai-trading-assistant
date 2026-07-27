"""데스크톱 배포(app/deploy.py) 경합 처리 — run_desktop.bat의 「커밋+푸시」 경로 검증.

main은 여러 주체가 같은 생성물을 쓴다(뉴스 30분·매크로 60분 CI + 데스크톱 배포, 그리고
이 push가 깨우는 trades/morning 워크플로 자신). 그래서 배포는 두 가지를 견뎌야 한다 —
생성물 rebase 충돌, 그리고 흡수와 push 사이에 원격이 먼저 갱신되는 non-fast-forward 거부.
"""
from __future__ import annotations

import subprocess
import sys
import types

import pytest

from app import deploy

_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(cwd, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                         env={**_ENV, "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)})
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """bare 원격 + 작업 클론. deploy가 이 클론에서 동작하도록 BASE_DIR를 갈아끼운다."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    (work / "docs").mkdir()
    (work / "data").mkdir()
    (work / "docs" / "index.html").write_text("base", encoding="utf-8")
    (work / "data" / "trades.json").write_text("[]", encoding="utf-8")
    _git(work, "add", "docs", "data")
    _git(work, "commit", "-m", "base")
    _git(work, "push", "-q", "origin", "main")

    monkeypatch.setattr(deploy, "BASE_DIR", work)
    monkeypatch.setattr(deploy.time, "sleep", lambda _s: None)  # 재시도 백오프 대기 제거
    # deploy가 함수 안에서 임포트하는 재빌드(build.run_build)는 여기선 대상이 아니다.
    stub = types.ModuleType("build")
    stub.run_build = lambda target: []
    monkeypatch.setitem(sys.modules, "build", stub)
    return remote, work


def _remote_log(remote) -> list[str]:
    return _git(remote, "log", "--format=%s", "main").splitlines()


def _competing_push(tmp_path, remote, text: str, message: str) -> None:
    """다른 주체(CI 봇)가 같은 생성물을 먼저 갱신해 push한 상황을 만든다."""
    other = tmp_path / f"other-{message.replace(' ', '_')}"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    (other / "docs" / "index.html").write_text(text, encoding="utf-8")
    _git(other, "add", "docs")
    _git(other, "commit", "-m", message)
    _git(other, "push", "-q", "origin", "main")


def test_no_change_skips_commit(repo):
    remote, _work = repo
    assert deploy.commit_and_push("chore(desktop): sync") is False
    assert _remote_log(remote) == ["base"]


def test_absorbs_conflicting_remote_commit(tmp_path, repo):
    """★회귀: 원격이 같은 생성물을 먼저 바꿔도 배포는 충돌로 죽지 않는다."""
    remote, work = repo
    _competing_push(tmp_path, remote, "CI가 만든 산출물", "chore(news): update")
    (work / "docs" / "index.html").write_text("데스크톱이 만든 산출물", encoding="utf-8")

    assert deploy.commit_and_push("chore(desktop): sync") is True
    log = _remote_log(remote)
    assert log[0] == "chore(desktop): sync"
    assert "chore(news): update" in log  # 원격 커밋을 덮지 않고 그 위에 쌓였다


def test_retries_when_remote_wins_the_race(tmp_path, repo, monkeypatch):
    """★회귀: 흡수와 push 사이에 원격이 먼저 갱신되면 재시도해서 배포를 완료한다.

    거부 한 번에 포기하면 동기화 결과(매매일지·자산 암호문)가 로컬에만 남는다.
    """
    remote, work = repo
    (work / "docs" / "index.html").write_text("데스크톱이 만든 산출물", encoding="utf-8")

    real_git = deploy._git
    pushes: list[int] = []

    def racing_git(*args: str, check: bool = True):
        # 첫 push 직전에 원격을 한 발 앞세워 non-fast-forward 거부를 만든다.
        if args and args[0] == "push":
            pushes.append(1)
            if len(pushes) == 1:
                _competing_push(tmp_path, remote, "CI가 선점", "chore(macro): update")
        return real_git(*args, check=check)

    monkeypatch.setattr(deploy, "_git", racing_git)

    assert deploy.commit_and_push("chore(desktop): sync") is True
    assert len(pushes) == 2, "거부 후 재시도가 일어나야 한다"
    log = _remote_log(remote)
    assert log[0] == "chore(desktop): sync"
    assert "chore(macro): update" in log


def test_gives_up_loudly_after_retries(tmp_path, repo, monkeypatch):
    """계속 거부되면 조용히 성공한 척하지 않고 실패를 알린다(커밋은 로컬에 남는다)."""
    remote, work = repo
    (work / "docs" / "index.html").write_text("데스크톱이 만든 산출물", encoding="utf-8")

    real_git = deploy._git
    n = 0

    def always_racing_git(*args: str, check: bool = True):
        nonlocal n
        if args and args[0] == "push":
            n += 1
            _competing_push(tmp_path, remote, f"CI가 선점 {n}", f"chore(macro): update {n}")
        return real_git(*args, check=check)

    monkeypatch.setattr(deploy, "_git", always_racing_git)
    monkeypatch.setattr(deploy, "PUSH_RETRIES", 2)

    with pytest.raises(RuntimeError):
        deploy.commit_and_push("chore(desktop): sync")
    assert n == 2
    assert _remote_log(remote)[0] == "chore(macro): update 2"
