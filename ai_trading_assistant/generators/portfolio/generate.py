"""Portfolio 생성 → docs/portfolio/index.html(design/09, design/20 Phase 8).

Asset과 같은 암호문(docs/data/asset/assets.enc.json)을 재사용한다 — 별도로 수집·암호화하지
않는다. 두 페이지가 같은 파일을 같은 게이트 세션(sessionStorage)으로 열람하는 것이
"Asset·Portfolio는 동일 게이트 세션을 공유한다"(design/08 §1)는 계약의 실제 구현이다.
이 생성기 자체는 게이트 셸만 렌더한다 — 실제 숫자는 static/js/portfolio.js가 클라이언트에서
복호화해 채운다(design/20 Phase 8 DoD 1).
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    return render(
        "pages/portfolio.html",
        {
            "root": "..",
            "nav": nav.context(active="portfolio"),
            "generated_at": fmt_kst(now_kst()) + " KST",
        },
        DOCS_DIR / "portfolio" / "index.html",
    )
