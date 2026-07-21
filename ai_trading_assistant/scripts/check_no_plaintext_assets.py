"""자산 평문 유출 가드(design/20 Phase 8 DoD 1) — pre-commit·CI 양쪽이 동일 로직을 재사용한다.

한쪽 가드만 있으면 무력화된다(로컬 훅은 클론마다 수동 설치, github-actions bot 커밋은 훅을
거치지 않음) — 그래서 이 스크립트 하나를 두 곳에서 그대로 호출한다(design/20 Phase 8 §리스크).

검사 대상: (1) 민감 키에 원시 숫자값이 붙은 JSON 패턴(자산 절대금액 역산 가능) (2) data/snapshots/
경로 자체(로컬 전용 원장, 커밋 금지). 민감 키 목록은 repositories/asset_repository.py의 평문
필드명과 동기화해야 한다 — 이 파일이 유일한 검사 기준이다.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# design/20 Phase 8: 총자산·계좌 잔고·목표금액·투입원금 등 절대 금액을 담는 필드명.
# 신규 필드를 repositories/asset_repository.py에 추가할 때 이 목록도 함께 갱신해야 한다.
SENSITIVE_KEYS = (
    "balance", "total_assets", "goal_amount", "principal", "invested_principal",
    "cash_balance", "eval_amount", "krw_amount", "usd_amount", "usdt_amount",
    "account_value", "realized_pnl_amount",
)
_KEY_NUMBER_RE = re.compile(r'"(' + "|".join(SENSITIVE_KEYS) + r')"\s*:\s*-?\d{4,}(\.\d+)?')
_SNAPSHOT_PATH_RE = re.compile(r"(^|/)data/snapshots/")

# 내용(원시 금액 패턴) 스캔 제외 대상 — 테스트 픽스처와 가드 자신의 소스는 합성(가짜) 금액을
# 의도적으로 포함한다(가드·암호화가 실제로 동작하는지 검증하려면 필수). 실제 자산 절대값은
# docs/(발행물)·data/snapshots/(로컬 원장)에만 존재하므로, 이 두 곳은 여전히 스캔된다:
# data/snapshots/는 아래 경로 차단으로, docs/는 CI 액션이 docs/만 인자로 넘겨 스캔한다.
_CONTENT_SCAN_EXCLUDE_RE = re.compile(r"(^|/)(tests|scripts)/")


def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in out.stdout.splitlines() if f]


def check_paths(paths: list[str]) -> list[str]:
    """위반 목록(빈 리스트=통과). 경로 문자열 자체와 각 파일 내용을 검사한다."""
    violations: list[str] = []
    for p in paths:
        norm = p.replace("\\", "/")
        if _SNAPSHOT_PATH_RE.search(norm):
            violations.append(f"{p}: data/snapshots/ 경로는 커밋 금지(로컬 전용 원장, .gitignore 대상)")
            continue
        if _CONTENT_SCAN_EXCLUDE_RE.search(norm):
            continue  # 테스트 픽스처·가드 소스는 합성 금액을 의도적으로 포함(위 주석 참조)
        path = Path(p)
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        m = _KEY_NUMBER_RE.search(text)
        if m:
            violations.append(f"{p}: 평문 금액 패턴 발견 — 키 \"{m.group(1)}\"에 원시 숫자값이 그대로 있음")
    return violations


def main(argv: list[str]) -> int:
    paths = argv[1:] if len(argv) > 1 else _staged_files()
    violations = check_paths(paths)
    if violations:
        print("자산 평문 유출 가드 실패 — 아래 항목을 확인하세요(design/20 Phase 8 DoD 1):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
