"""Phase 1 v2 셸 검증용 스켈레톤 라우트 → docs/v2/index.html. nav 미노출(design/20 Phase 1 DoD)."""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    out = DOCS_DIR / "v2" / "index.html"
    render(
        "pages/skeleton_v2.html",
        {
            "root": "..",
            "nav": nav.context(active="__v2_preview__"),  # 어떤 메뉴 항목과도 일치하지 않음(비노출)
            "generated_at": fmt_kst(now_kst()) + " KST",
        },
        out,
    )
    return out
