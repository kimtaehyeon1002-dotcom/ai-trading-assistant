"""런처(첫 화면) 생성 → docs/index.html.

이동만 담당하는 화면이라 **데이터 파이프라인을 타지 않는다** — 시세·뉴스를 부르지 않으므로
네트워크 실패가 첫 화면을 깨뜨릴 수 없다. 표시하는 시각도 빌드 시각뿐이다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators.base import render
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    ctx = {
        "root": ".",
        "nav": nav.context(active=nav.LAUNCHER_KEY),
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    return render("pages/launcher.html", ctx, DOCS_DIR / "index.html")
