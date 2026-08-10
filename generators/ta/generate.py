"""Technical Analysis 페이지 생성 — docs/ta/index.html (지표·JSON 발행은 파이프라인이 담당).

design/20 Phase 2(수직 슬라이스 파일럿).
design/25 Phase B: 수집·검증·발행은 pipelines.get_ta()로 이동했다 — 이 모듈은 렌더만 한다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from repositories import ta_repository
from utils import sparkline
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    bundle = pipelines.get_ta()
    preview, closes = bundle["preview"], bundle["closes"]
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
            # 폴백 SVG와 클라이언트 차트가 같은 60일 구간을 보게 한다(utils.sparkline.window 단일 지점).
            "chart_closes": sparkline.window(closes, 60) if closes else [],
            "chart_dates": sparkline.window(bundle.get("dates") or [], 60) if closes else [],
        },
        out,
    )
    return out
