"""워커 실행 기록 — AI Office의 데이터원(사실만: 상태/시간/건수/에러. 지능 시뮬레이션 금지).

빌드 프로세스 동안 in-memory로 쌓고, generators/ai_office 가 이전 기록(runlog.json)과
병합해 발행한다. 상태 어휘: completed | error | skipped (정적 사이트라 running은 기록 불가).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, TypeVar

from utils.dates import now_kst

T = TypeVar("T")

_records: dict[str, dict] = {}


def run_step(worker: str, fn: Callable[[], T], *, fallback: T = None) -> T:
    """fn 실행을 계측: 성공=completed(+items), 예외=error(+메시지) 후 fallback 반환.

    같은 실행에서 이미 completed로 기록된 워커는 재계측하지 않는다
    (collectors 메모 히트가 실측 시간을 0ms로 덮어쓰는 것 방지 — 최초 실측만 사실로 유지).
    """
    if _records.get(worker, {}).get("status") == "completed":
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return fallback
    started = perf_counter()
    rec: dict[str, Any] = {"worker": worker, "last_run": now_kst().isoformat()}
    try:
        result = fn()
        rec["status"] = "completed"
        try:
            rec["items"] = len(result)  # type: ignore[arg-type]
        except TypeError:
            rec["items"] = None
        out = result
    except Exception as exc:  # noqa: BLE001 - 파이프라인은 부분 실패 허용, 사실대로 기록
        rec["status"] = "error"
        rec["last_error"] = str(exc)[:300]
        out = fallback
    rec["duration_ms"] = int((perf_counter() - started) * 1000)
    _records[worker] = rec
    return out


def note(worker: str, *, status: str = "completed", items: int | None = None, detail: str = "") -> None:
    """계산 없이 상태만 기록(예: 토큰 미설정으로 skipped)."""
    _records[worker] = {
        "worker": worker,
        "status": status,
        "items": items,
        "detail": detail,
        "duration_ms": 0,
        "last_run": now_kst().isoformat(),
    }


def records() -> dict[str, dict]:
    return dict(_records)


def merge_by_recency(a: dict, b: dict) -> dict:
    """워커 기록 두 벌을 **워커별 last_run이 더 최신인 쪽**으로 합친다.

    runlog.json은 CI(워크플로 6종)와 데스크톱이 같은 파일에 쓰는 공유 원장이다. 한쪽이
    자기 로컬 사본을 기준으로 통째로 덮어쓰면, 상대가 기록한 워커가 조용히 **사라진다**
    (실제 사고: 2026-07-28 데스크톱 sync가 CI의 "FS DART corpCode"·"FS EDGAR CIK맵" 기록을
    삭제 — design/26 Phase A에서 루프 센서가 검출).

    단순 `{**remote, **local}`은 반대 방향의 오염을 만든다 — 데스크톱이 돌리지 않는 워커는
    로컬 사본에 **낡은** 기록이 남아 있어, 그걸 우선하면 원격의 최신 기록을 과거로 되돌린다
    (센서가 가짜 stale 위반을 낸다). 그래서 위치가 아니라 시각으로 고른다.
    """
    merged = dict(a)
    for name, rec in b.items():
        cur = merged.get(name)
        if not isinstance(cur, dict) or not isinstance(rec, dict):
            merged[name] = rec
            continue
        merged[name] = rec if _last_run_key(rec) >= _last_run_key(cur) else cur
    return merged


def _last_run_key(rec: dict) -> datetime:
    """정렬용 last_run — 없거나 깨진 값은 최소값으로 취급(기록이 있는 쪽에 밀린다).

    naive/aware가 섞이면 비교 자체가 TypeError라, 파싱 결과는 항상 aware로 정규화한다.
    """
    try:
        dt = datetime.fromisoformat(str(rec.get("last_run", "")))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
