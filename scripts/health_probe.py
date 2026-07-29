"""루프 센서 — SLO(config/slo.py) 대비 실측 위반 목록 산출. design/26 §3-2.

**LLM이 없다.** 결정론적이라 비용이 0이고, 같은 입력이면 항상 같은 위반 목록이 나온다.
이 성질이 루프 전체의 신뢰 기반이다 — 판정이 흔들리면 그 위에 얹는 자동수정도 흔들린다.

    python -m scripts.health_probe            # 콘솔 요약 + ops/health/latest.json 기록
    python -m scripts.health_probe --check    # 위반이 있으면 exit 1 (CI 게이트용)
    python -m scripts.health_probe --json     # stdout으로 JSON (파일 기록 없음)

입력 축(design/26 §3-2 중 Phase A 구현분):
  ① docs/ai-office/runlog.json — 워커 실행 기록(status/last_run/items/last_error)
  ② gh run list                — 워크플로 최근 이력. gh가 없으면 이 축만 조용히 빠진다(사실대로 기록)

산출물 신선도(docs/data/**) 축은 Phase A에서 **구현하지 않는다** — CI 체크아웃에서는 파일 mtime이
체크아웃 시각이라 무의미하고, 발행 JSON에 공통 타임스탬프 규약이 없다(rankings.json은 as_of가
있고 ta/preview.json은 없다). 워커 기록이 같은 사건을 정확한 시각으로 이미 담고 있으므로,
부정확한 축을 추가해 오탐을 만드느니 뺀다(design/26 Phase A DoD "오탐 0").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:  # `python scripts/health_probe.py` 직접 실행 지원
    sys.path.insert(0, str(BASE_DIR))

from config import slo  # noqa: E402
from config.settings import BASE_DIR as REPO_DIR  # noqa: E402
from config.settings import DOCS_DIR  # noqa: E402
from utils.dates import now_kst, spans_weekend, to_kst  # noqa: E402
from utils.jsonio import load_json, save_json  # noqa: E402

RUNLOG_PATH = DOCS_DIR / "ai-office" / "runlog.json"
HEALTH_PATH = REPO_DIR / "ops" / "health" / "latest.json"

# gh가 실패로 세는 결론. cancelled/skipped는 중립으로 두고 연속 카운트를 **중단**한다
# (동시성 취소·조건부 skip을 장애로 오인하지 않기 위한 보수적 선택).
_FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})
_NEUTRAL_CONCLUSIONS = frozenset({"cancelled", "skipped", "action_required", "neutral", ""})


def _slug(name: str) -> str:
    """워커명 → 브랜치명에 쓸 수 있는 ascii 슬러그.

    워커명에 한글·공백이 섞여 있어(예: "Asset KIS 위탁") 그대로는 `fix/<id>` 브랜치명이 되지
    않는다. ascii 부분만 남기고, 한글이 탈락해 충돌·공백이 생길 수 있으므로 원본 이름의
    해시 4자를 덧붙여 유일성을 보장한다. 같은 이름이면 항상 같은 슬러그다(원장의 전제).
    """
    ascii_part = "-".join(re.findall(r"[a-z0-9]+", name.lower()))
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    lossy = len(re.sub(r"[^A-Za-z0-9\s]", "", name)) != len(name)
    return f"{ascii_part}-{digest}" if (lossy or not ascii_part) else ascii_part


def _violation(vid, severity, subject, rule, observed, expected, *, tier=slo.TIER_CLOUD,
               owner="", note="") -> dict:
    return {
        "id": vid, "severity": severity, "subject": subject, "rule": rule,
        "observed": observed, "expected": expected, "tier": tier, "owner": owner, "note": note,
    }


def _parse_ts(raw) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return to_kst(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _age_limit_h(spec: slo.WorkerSLO, last_run: datetime, now: datetime) -> float:
    """이번 구간에 적용할 상한(h) — 구간에 주말이 끼면 주말 상한.

    호출부가 "주말 상한조차 넘었다"를 먼저 판정하므로 spans_weekend의 일 단위 순회는
    상한 일수 이내로 제한된다(무한 루프 방지 — market_validator._night_max_age_h와 같은 형태).
    """
    if spec.max_age_weekend_h is None:
        return float(spec.max_age_h)
    return float(spec.max_age_weekend_h if spans_weekend(last_run, now) else spec.max_age_h)


def _fmt_age(hours: float) -> str:
    return f"{int(hours)}h{int((hours % 1) * 60):02d}m"


def check_workers(workers: dict, now: datetime) -> list[dict]:
    """runlog 기록 × SLO → 위반 목록."""
    violations: list[dict] = []

    for name, spec in slo.WORKERS.items():
        rec = workers.get(name)
        sid = _slug(name)
        common = {"tier": spec.tier, "owner": spec.owner, "note": spec.note}

        if not isinstance(rec, dict):
            violations.append(_violation(
                f"w.{sid}.missing", "major", name, "runlog 등재",
                "기록 없음", "runlog.json에 워커 기록 존재", **common,
            ))
            continue

        status = rec.get("status")
        if status not in spec.status_ok:
            # error는 이미 발행물이 틀어졌다는 뜻 → critical. 그 외 예상 밖 상태는 major
            severity = "critical" if status == "error" else "major"
            detail = rec.get("last_error") or rec.get("detail") or ""
            violations.append(_violation(
                f"w.{sid}.status", severity, name, "허용 상태",
                f"{status}" + (f" — {detail[:120]}" if detail else ""),
                " | ".join(spec.status_ok), **common,
            ))

        last_run = _parse_ts(rec.get("last_run"))
        if spec.cadence_min is not None and spec.max_age_h is not None:
            if last_run is None:
                violations.append(_violation(
                    f"w.{sid}.stale", "major", name, "last_run 파싱",
                    f"해석 불가: {rec.get('last_run')!r}", "ISO8601 타임스탬프", **common,
                ))
            else:
                age_h = (now - last_run).total_seconds() / 3600
                hard_limit = float(spec.max_age_weekend_h or spec.max_age_h)
                limit = hard_limit if age_h > hard_limit else _age_limit_h(spec, last_run, now)
                if age_h > limit:
                    violations.append(_violation(
                        f"w.{sid}.stale", "major", name, f"max_age {limit:g}h",
                        f"{_fmt_age(age_h)} 경과 (last_run {rec.get('last_run', '')[:16]})",
                        f"{limit:g}h 이내", **common,
                    ))

        if spec.min_items is not None and status == "completed":
            items = rec.get("items")
            if isinstance(items, int) and items < spec.min_items:
                violations.append(_violation(
                    f"w.{sid}.items", "major", name, f"min_items {spec.min_items}",
                    f"{items}건", f"{spec.min_items}건 이상", **common,
                ))

    # SLO에 없는 워커 — 표가 코드보다 뒤처졌다는 신호(신규 워커 등재 누락)
    for name in workers:
        if name not in slo.WORKERS:
            violations.append(_violation(
                f"w.{_slug(name)}.undeclared", "minor", name, "SLO 등재",
                "runlog에는 있으나 config/slo.py에 없음", "config/slo.py WORKERS에 선언",
                note="신규 워커 추가 시 SLO 표도 함께 갱신해야 한다",
            ))

    return violations


def _gh_runs(workflow: str, limit: int) -> list[dict] | None:
    """gh run list 결과. gh 부재·인증 실패·저장소 밖이면 None(추정하지 않는다)."""
    try:
        out = subprocess.run(
            ["gh", "run", "list", "--workflow", workflow, "--limit", str(limit),
             "--json", "conclusion,status,createdAt,displayTitle"],
            capture_output=True, text=True, timeout=60, cwd=REPO_DIR,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    try:
        data = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def check_workflows() -> tuple[list[dict], str]:
    """워크플로 연속 실패 → (위반 목록, 축 상태 문자열)."""
    violations: list[dict] = []
    probed = 0
    for wf, spec in slo.WORKFLOWS.items():
        runs = _gh_runs(wf, slo.WORKFLOW_LOOKBACK)
        if runs is None:
            continue
        probed += 1
        streak = 0
        for run in runs:
            if run.get("status") != "completed":
                continue  # 진행 중인 실행은 아직 판정 대상이 아니다
            conclusion = (run.get("conclusion") or "").lower()
            if conclusion in _FAILED_CONCLUSIONS:
                streak += 1
                continue
            break  # 성공이든 중립이든 연속 실패는 여기서 끊긴다
        threshold = spec["max_consecutive_failures"]
        if streak >= threshold:
            violations.append(_violation(
                f"wf.{wf.replace('.yml', '')}.fail", "critical", wf, f"연속 실패 < {threshold}",
                f"최근 {streak}회 연속 실패", f"{threshold}회 미만", owner=wf, note=spec["desc"],
            ))
    if probed == 0:
        return [], "unavailable — gh CLI 없음/미인증/저장소 밖 (이 축은 판정하지 않음)"
    return violations, f"ok — 워크플로 {probed}/{len(slo.WORKFLOWS)}종 조회"


def probe(*, runlog_path: Path = RUNLOG_PATH, now: datetime | None = None,
          with_workflows: bool = True) -> dict:
    now = now or now_kst()
    runlog_data = load_json(runlog_path, default=None)
    if isinstance(runlog_data, dict) and isinstance(runlog_data.get("workers"), dict):
        workers = runlog_data["workers"]
        runlog_state = f"ok — 워커 {len(workers)}종, updated_at {runlog_data.get('updated_at', '?')[:16]}"
    else:
        workers = {}
        runlog_state = f"missing — {runlog_path} 없음/형식 오류"

    violations = check_workers(workers, now)
    if with_workflows:
        wf_violations, wf_state = check_workflows()
        violations += wf_violations
    else:
        wf_state = "skipped — --no-gh"

    violations.sort(key=lambda v: (slo.SEVERITY_ORDER.index(v["severity"]), v["id"]))
    return {
        "probed_at": now.isoformat(),
        "sources": {"runlog": runlog_state, "workflows": wf_state},
        "counts": {s: sum(1 for v in violations if v["severity"] == s) for s in slo.SEVERITY_ORDER},
        "violations": violations,
    }


def _print_report(result: dict) -> None:
    counts = result["counts"]
    print(f"루프 센서 — {result['probed_at'][:19]}")
    for axis, state in result["sources"].items():
        print(f"  [{axis}] {state}")
    total = sum(counts.values())
    if total == 0:
        print("  위반 없음 — 선언된 SLO를 모두 만족합니다.")
        return
    print(f"  위반 {total}건 (critical {counts['critical']} · major {counts['major']} · minor {counts['minor']})")
    for v in result["violations"]:
        tier = " [desktop]" if v["tier"] == slo.TIER_DESKTOP else ""
        print(f"    - [{v['severity']}]{tier} {v['subject']} / {v['rule']}")
        print(f"        관측: {v['observed']}")
        print(f"        기대: {v['expected']}   ({v['id']})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="루프 센서 — SLO 대비 실측 위반 산출(design/26)")
    ap.add_argument("--check", action="store_true", help="위반이 하나라도 있으면 exit 1")
    ap.add_argument("--json", action="store_true", help="stdout에 JSON 출력(파일 기록 안 함)")
    ap.add_argument("--no-gh", action="store_true", help="워크플로 축 생략(오프라인/로컬)")
    args = ap.parse_args(argv)

    # Windows 콘솔 기본 코드페이지(cp949)에는 '—' 같은 문자가 없어 리포트 출력이 죽는다.
    # 진단 도구가 인코딩 때문에 실패하면 본말전도이므로 stdout을 UTF-8로 고정한다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    result = probe(with_workflows=not args.no_gh)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        save_json(HEALTH_PATH, result)
        _print_report(result)
        print(f"  → {HEALTH_PATH.relative_to(REPO_DIR)}")

    return 1 if (args.check and sum(result["counts"].values())) else 0


if __name__ == "__main__":
    raise SystemExit(main())
