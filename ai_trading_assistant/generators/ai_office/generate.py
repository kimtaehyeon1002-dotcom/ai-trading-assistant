"""AI Office 생성 → docs/ai-office/index.html + runlog.json.

각 워커 = 실제 시스템 모듈 1개. 사실만 표시(상태/시간/건수/에러) — 지능 시뮬레이션·
가짜 진행률 금지. 이전 runlog.json(발행물)과 이번 실행 기록을 병합해 마지막 상태를 유지.

design/20 Phase 9: v2 셸로 치환됐다(v1 셸 은퇴의 선행 조건 — 이 페이지가 유일하게 남은 v1 셸
라이브 의존이었다). v1 템플릿과 v1 공용 셸 자체가 이 Phase에서 함께 소스 은퇴했으므로(git
히스토리에서 복원 가능), 더 이상 템플릿명만 되돌리는 방식의 롤백은 불가능하다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
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
        "root": "..",
        "nav": nav.context(active="office"),
        "workers": rows,
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    out = render("pages/ai_office_v2.html", ctx, DOCS_DIR / "ai-office" / "index.html")
    log.info("AI Office 생성: %s", out)
    return out
