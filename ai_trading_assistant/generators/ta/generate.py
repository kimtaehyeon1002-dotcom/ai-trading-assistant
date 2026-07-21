"""Technical Analysis 페이지 생성 — KOSPI 프리뷰 지표 계산 + docs/ta/index.html + docs/data/ta/preview.json.

design/20 Phase 2(수직 슬라이스 파일럿). 데이터는 pipelines 계층 관례를 따라
collectors → validators → repositories 순으로만 취득한다.
"""
from __future__ import annotations

from pathlib import Path

from collectors import ta_collector
from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from repositories import ta_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst
from validators import ta_validator


def _build_preview() -> tuple[dict | None, list[float]]:
    raw = runlog.run_step("TA Analyst", ta_collector.collect_kospi_daily, fallback=None)
    rows = ta_validator.validate(raw)
    if not rows:
        return None, []
    body = ta_repository.build(rows)
    ta_repository.persist(body)
    return body, [r["close"] for r in rows]


def generate() -> Path:
    preview, closes = _build_preview()
    out = DOCS_DIR / "ta" / "index.html"
    render(
        "pages/ta.html",
        {
            "root": "..",
            "nav": nav.context(active="ta"),
            "generated_at": fmt_kst(now_kst()) + " KST",
            "preview": preview,
            "freshness": ta_repository.freshness_attrs(preview["close"]["as_of_iso"]) if preview else None,
            "sparkline_svg": ta_repository.sparkline_svg(closes) if closes else "",
        },
        out,
    )
    return out
