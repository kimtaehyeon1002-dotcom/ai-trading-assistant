"""Jinja2 환경 + 렌더/정적복사 유틸. 모든 생성기가 공유."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import DOCS_DIR, SITE, STATIC_DIR, TEMPLATES_DIR
from utils.dates import fmt_kst


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


def _arrow(v: Any) -> str:
    """등락 화살표 — 색과 항상 병행 표기(R4, design/00 §2-6)."""
    if v is None:
        return ""
    return "▲" if v >= 0 else "▼"


def _pctv2(v: Any) -> str:
    """등락률(v2 전용) — 진짜 마이너스 U+2212 사용(design/00 §3-3). v1의 pct 필터는 동결 대상이라
    별도 필터로 분리한다(공유 필터를 고치면 v1 렌더 결과가 바뀌어 Phase 1 회귀 계약이 깨진다)."""
    if v is None:
        return "—"
    sign = "+" if v >= 0 else "−"
    return f"{sign}{abs(v):.2f}%"


def _amount_kr(v: Any) -> str:
    """거래대금(원) → 억원 단위 표기(design/21 §7-1 TOP30 테이블, v2 전용)."""
    if v is None:
        return "—"
    return f"{v / 1e8:,.0f}억"


def _amount_usd(v: Any) -> str:
    """거래대금(USD) → $B/$M 단위 표기(design/21 §7-1 TOP30 테이블, v2 전용)."""
    if v is None:
        return "—"
    return f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.0f}M"


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.globals["site"] = SITE
_env.filters.update(
    pct=_pct, signclass=_signclass, price=_price, money=_money, kst=_kst, arrow=_arrow, pctv2=_pctv2,
    amount_kr=_amount_kr, amount_usd=_amount_usd,
)


def render(template: str, context: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _env.get_template(template).render(**context)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def copy_static() -> None:
    """static/ → docs/static/ 복사(파일 추가·갱신만, 삭제 없음) + .nojekyll(Jekyll 비활성).

    design/20 Phase 9: 예전에는 dst를 통째로 rmtree한 뒤 새로 복사했으나, v1 전용 정적 자산을
    소스에서 제거한 뒤에도 동결 아카이브(docs/morning/2026-07-01/ 등)가 그 배포본을 계속
    참조한다(§0-1 정본 4 "은퇴는 소스 한정"). rmtree를 없애 dst에 이미 있는 파일은 소스에
    없어도 남도록 한다 — 새 v2 정적 자산만 추가/갱신되고 과거 배포물은 보존된다.
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dst = DOCS_DIR / "static"
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, dst, dirs_exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
