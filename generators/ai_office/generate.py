"""AI Office 생성 → docs/ai-office/index.html + runlog.json.

각 워커 = 실제 시스템 모듈 1개. 사실만 표시(상태/시간/건수/에러) — 지능 시뮬레이션·
가짜 진행률 금지. 이전 runlog.json(발행물)과 이번 실행 기록을 병합해 마지막 상태를 유지.
"""
from __future__ import annotations

from pathlib import Path

from config.settings import DOCS_DIR
from generators.base import render
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("gen.ai_office")

_RUNLOG = DOCS_DIR / "ai-office" / "runlog.json"

# 워커 = 실제 모듈 매핑(존재하는 모듈만 등록)
WORKERS: list[tuple[str, str]] = [
    ("Data Officer", "시장 지표 수집·검증 (collectors/market·kiwoom)"),
    ("News Research", "뉴스 수집·검증·병합 (collectors/news)"),
    ("Theme Analyst", "테마 빈도 산출 (calculators/themes)"),
    ("Trade Manager", "매매 원장 로드 (repositories/trade)"),
    ("Notion Sync", "Notion ERP 동기화 (collectors/notion)"),
    ("Publisher", "페이지 생성·발행 (generators)"),
]


def generate() -> Path:
    prev = load_json(_RUNLOG, default={}) or {}
    if not isinstance(prev, dict):
        prev = {}
    merged = {**prev.get("workers", {}), **runlog.records()}
    save_json(_RUNLOG, {"updated_at": now_kst().isoformat(), "workers": merged})

    rows = []
    for name, desc in WORKERS:
        rec = merged.get(name)
        rows.append(
            {
                "name": name,
                "desc": desc,
                "status": rec.get("status", "idle") if rec else "idle",
                "items": rec.get("items") if rec else None,
                "duration_ms": rec.get("duration_ms") if rec else None,
                "last_run": rec.get("last_run", "") if rec else "",
                "last_error": rec.get("last_error", "") if rec else "",
                "detail": rec.get("detail", "") if rec else "",
            }
        )

    ctx = {
        "active": "office",
        "root": "..",
        "workers": rows,
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    out = render("ai_office.html", ctx, DOCS_DIR / "ai-office" / "index.html")
    log.info("AI Office 생성: %s", out)
    return out
