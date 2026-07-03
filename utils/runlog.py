"""워커 실행 기록 — AI Office의 데이터원(사실만: 상태/시간/건수/에러. 지능 시뮬레이션 금지).

빌드 프로세스 동안 in-memory로 쌓고, generators/ai_office 가 이전 기록(runlog.json)과
병합해 발행한다. 상태 어휘: completed | error | skipped (정적 사이트라 running은 기록 불가).
"""
from __future__ import annotations

from collections.abc import Callable
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
