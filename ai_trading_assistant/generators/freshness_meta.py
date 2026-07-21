"""docs/data/meta/freshness.json 발행 — Settings ④(데이터 갱신 안내)의 단일 fetch 소스.

design/21 §4: "runlog는 그 생성 원료" — ai_office.generate()가 이전 runlog.json과 이번 실행
기록을 병합해 발행한 결과물을 그대로 읽어 재구성한다(병합 로직을 여기서 중복하지 않는다).
반드시 gen_office() 이후(build.py 공통 마무리 단계)에 호출해야 정확하다.
"""
from __future__ import annotations

from config.settings import DOCS_DIR
from utils.dates import now_kst
from utils.jsonio import load_json, save_json

# worker → 기대 갱신 주기(분). 매핑 없는 워커는 expected_T_min=None(정책 미정)으로 정직하게 표기.
_EXPECTED_T_MIN: dict[str, int] = {
    "TA Analyst": 24 * 60,
    "Data Officer": 30,
    "News Research": 30,
    "Theme Analyst": 30,
}


def generate() -> None:
    runlog_data = load_json(DOCS_DIR / "ai-office" / "runlog.json", default={}) or {}
    workers = runlog_data.get("workers", {}) if isinstance(runlog_data, dict) else {}

    sources = {
        name: {
            "status": rec.get("status"),
            "last_built": rec.get("last_run"),
            "expected_T_min": _EXPECTED_T_MIN.get(name),
            "items": rec.get("items"),
            "duration_ms": rec.get("duration_ms"),
        }
        for name, rec in workers.items()
        if isinstance(rec, dict)
    }
    save_json(
        DOCS_DIR / "data" / "meta" / "freshness.json",
        {"generated_at": now_kst().isoformat(), "sources": sources},
    )
