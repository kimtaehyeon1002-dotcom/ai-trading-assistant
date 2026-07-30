"""원격 runlog 기록을 로컬 runlog에 되살린다 — 데스크톱 배포와 CI push가 공유하는 단일 구현.

`docs/ai-office/runlog.json`은 GitHub Actions 6종과 데스크톱이 같이 쓰는 **누적 원장**이다.
생성물(docs/**)은 rebase에서 한쪽을 골라도 재빌드로 정정되지만, 이 파일은 재빌드로 복원되지
않는다 — 고르는 순간 상대가 기록한 워커가 영구히 사라진다.

실제 사고 2건이 이 모듈의 존재 이유다:
  · 2026-07-28 데스크톱 sync가 CI의 `FS DART corpCode`·`FS EDGAR CIK맵` 기록을 삭제
    (app/deploy.py의 `rebase -X theirs`가 데스크톱 사본을 채택) — h.build-ci.runlog-overwrite
  · CI의 commit-push 액션도 `-X theirs`를 쓰므로 방향만 반대인 같은 유실이 가능하다
    — a.build-ci.rebase-conflict-push의 전제 조건

병합은 위치가 아니라 **워커별 last_run 시각**으로 고른다. 단순 `{**remote, **local}`은 반대
방향의 오염을 만든다 — 자기가 돌리지 않는 워커의 낡은 기록이 상대의 최신 기록을 과거로 되돌리고,
그러면 루프 센서가 가짜 stale 위반을 낸다(design/26 §8-2).

    python -m scripts.merge_remote_runlog            # origin/main 기준
    python -m scripts.merge_remote_runlog --ref HEAD~1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:  # `python scripts/merge_remote_runlog.py` 직접 실행 지원
    sys.path.insert(0, str(BASE_DIR))

from config.settings import BASE_DIR as REPO_DIR  # noqa: E402
from config.settings import DOCS_DIR  # noqa: E402
from utils import runlog  # noqa: E402
from utils.jsonio import load_json, save_json  # noqa: E402

RUNLOG_REL = "docs/ai-office/runlog.json"
RUNLOG_PATH = DOCS_DIR / "ai-office" / "runlog.json"

DEFAULT_REF = "origin/main"


def _show(ref: str, rel_path: str, cwd: Path) -> dict | None:
    """`git show <ref>:<path>` → dict. 파일/ref 부재는 None(실패가 아니다)."""
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False,
        )
    except OSError:
        return None
    if out.returncode != 0 or not out.stdout:
        return None
    try:
        parsed = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def merge_from_ref(
    ref: str = DEFAULT_REF,
    *,
    path: Path | None = None,
    cwd: Path | None = None,
) -> int:
    """`ref`의 runlog를 로컬 runlog에 병합. 반환=되살아난 워커 수(0=변화 없음).

    로컬 파일이 없거나 ref를 읽을 수 없으면 아무것도 하지 않고 0을 반환한다 — 이 단계는
    배포를 막을 자격이 없다(기록 유실은 아프지만 발행 중단보다는 낫다).
    """
    path = path or RUNLOG_PATH
    cwd = cwd or REPO_DIR

    remote = _show(ref, RUNLOG_REL, cwd)
    if remote is None:
        return 0
    local = load_json(path, default=None)
    if not isinstance(local, dict):
        return 0

    local_workers = local.get("workers", {})
    merged = runlog.merge_by_recency(remote.get("workers", {}), local_workers)
    if merged == local_workers:
        return 0

    restored = len(merged) - len(local_workers)
    save_json(path, {**local, "workers": merged})
    return restored


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="원격 runlog 기록 병합(design/26 §8-2)")
    ap.add_argument("--ref", default=DEFAULT_REF, help=f"비교 대상 ref (기본 {DEFAULT_REF})")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    restored = merge_from_ref(args.ref)
    if restored > 0:
        print(f"runlog: {args.ref}의 워커 기록 {restored}종 복원")
    else:
        print("runlog: 병합할 원격 기록 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
