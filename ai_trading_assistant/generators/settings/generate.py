"""Settings 생성 → docs/settings/index.html(design/10, design/20 Phase 9).

이 페이지는 서버 데이터를 소비하지 않는다 — 모든 상태는 localStorage/sessionStorage(클라이언트)
이고, ④ 데이터 갱신 안내만 client-side fetch로 docs/data/meta/freshness.json을 읽는다
(design/20 Phase 2 최초 발행 파일 재사용). 그래서 generate()는 정적 셸만 렌더한다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    return render(
        "pages/settings.html",
        {
            "root": "..",
            "nav": nav.context(active="settings"),
            "generated_at": fmt_kst(now_kst()) + " KST",
        },
        DOCS_DIR / "settings" / "index.html",
    )
