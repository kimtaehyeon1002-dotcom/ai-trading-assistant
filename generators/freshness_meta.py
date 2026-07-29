"""docs/data/meta/freshness.json 발행 — Settings ④(데이터 갱신 안내)의 단일 fetch 소스.

design/21 §4: "runlog는 그 생성 원료" — ai_office.generate()가 이전 runlog.json과 이번 실행
기록을 병합해 발행한 결과물을 그대로 읽어 재구성한다(병합 로직을 여기서 중복하지 않는다).
반드시 gen_office() 이후(build.py 공통 마무리 단계)에 호출해야 정확하다.
"""
from __future__ import annotations

from config import slo
from config.settings import DOCS_DIR
from utils.dates import now_kst
from utils.jsonio import load_json, save_json

# 기대 갱신 주기(분)는 config/slo.py가 단일 기준이다(design/26 §3-1).
# 종전에는 여기 4종짜리 사본 테이블이 따로 있었고, 그중 Theme Analyst가 30분으로 적혀 있었다 —
# 이 워커는 morning 타깃에서만 호출되므로 실제로는 일1회다. Settings ④가 실제와 다른 기대치를
# 표시하던 결함이라 사본을 없애고 SLO를 직접 읽는다(나머지 17종은 애초에 표기 자체가 없었다).
# SLO에 없는 워커는 expected_T_min=None(정책 미정)으로 정직하게 표기한다.


def generate() -> None:
    runlog_data = load_json(DOCS_DIR / "ai-office" / "runlog.json", default={}) or {}
    workers = runlog_data.get("workers", {}) if isinstance(runlog_data, dict) else {}

    sources = {
        name: {
            "status": rec.get("status"),
            "last_built": rec.get("last_run"),
            "expected_T_min": getattr(slo.WORKERS.get(name), "cadence_min", None),
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
