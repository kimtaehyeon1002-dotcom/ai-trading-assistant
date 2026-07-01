"""Jinja2 환경 + 렌더/정적복사 유틸. 모든 생성기가 공유."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import DOCS_DIR, SITE, STATIC_DIR, TEMPLATES_DIR
from core.dates import fmt_kst


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _signclass(v: Any) -> str:
    if v is None:
        return "flat"
    return "up" if v >= 0 else "down"


def _price(v: Any) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


def _money(v: Any) -> str:
    if v is None or v == "":
        return "—"
    return f"{v:,.0f}"


def _kst(dt: Any) -> str:
    if not dt:
        return ""
    return fmt_kst(dt, "%m-%d %H:%M")


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.globals["site"] = SITE
_env.filters.update(pct=_pct, signclass=_signclass, price=_price, money=_money, kst=_kst)


def render(template: str, context: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _env.get_template(template).render(**context)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def copy_static() -> None:
    """static/ → docs/static/ 복사 + .nojekyll(Jekyll 비활성)."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dst = DOCS_DIR / "static"
    if dst.exists():
        shutil.rmtree(dst)
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, dst)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
