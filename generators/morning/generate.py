"""모닝리포트 페이지 생성 → docs/morning/YYYY-MM-DD/index.html + 아카이브 인덱스."""
from __future__ import annotations

from pathlib import Path

from config.settings import DOCS_DIR
from core.logging import get_logger
from generators.base import render
from services.report.morning import build_morning

log = get_logger("gen.morning")


def generate() -> Path:
    data = build_morning()
    out = DOCS_DIR / "morning" / data.date / "index.html"
    render("morning.html", {"active": "morning", "root": "../..", "data": data}, out)
    _archive()
    log.info("모닝리포트 생성: %s", out)
    return out


def _archive() -> None:
    base = DOCS_DIR / "morning"
    dates = (
        sorted(
            [p.name for p in base.iterdir() if p.is_dir() and p.name[:1].isdigit()],
            reverse=True,
        )
        if base.exists()
        else []
    )
    render("morning_index.html", {"active": "morning", "root": "..", "dates": dates}, base / "index.html")
