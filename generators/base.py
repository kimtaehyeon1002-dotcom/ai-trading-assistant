"""Jinja2 환경 + 렌더/정적복사 유틸. 모든 생성기가 공유."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, Undefined, FileSystemLoader, select_autoescape

from config.settings import DOCS_DIR, SITE, STATIC_DIR, TEMPLATES_DIR
from utils.dates import fmt_kst


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _missing(v: Any) -> bool:
    """결측 판정 — None과 Jinja Undefined를 같게 취급한다.

    design/25 Phase A의 last-good 폴백이 **과거 발행물의 항목을 되살리기** 때문에 필요하다.
    되살아난 항목은 그 시절 스키마라 지금 템플릿이 참조하는 키가 없을 수 있고, 그러면 접근
    결과가 Undefined다. Undefined는 `is not none` 검사를 통과해 버려서 숫자 필터로 흘러들고
    페이지 전체 렌더가 죽는다(실측으로 확인). 결측은 결측으로 다루는 것이 맞다.
    """
    return v is None or isinstance(v, Undefined)


def _signclass(v: Any) -> str:
    if _missing(v):
        return "flat"
    return "up" if v >= 0 else "down"


def _price(v: Any) -> str:
    if _missing(v):
        return "—"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


def _money(v: Any) -> str:
    if _missing(v) or v == "":
        return "—"
    return f"{v:,.0f}"


def _kst(dt: Any) -> str:
    if not dt:
        return ""
    return fmt_kst(dt, "%m-%d %H:%M")


def _arrow(v: Any) -> str:
    """등락 화살표 — 색과 항상 병행 표기(R4, design/00 §2-6)."""
    if _missing(v):
        return ""
    return "▲" if v >= 0 else "▼"


def _pctv2(v: Any) -> str:
    """등락률(v2 전용) — 진짜 마이너스 U+2212 사용(design/00 §3-3). v1의 pct 필터는 동결 대상이라
    별도 필터로 분리한다(공유 필터를 고치면 v1 렌더 결과가 바뀌어 Phase 1 회귀 계약이 깨진다)."""
    if _missing(v):
        return "—"
    sign = "+" if v >= 0 else "−"
    return f"{sign}{abs(v):.2f}%"


def _amount_kr(v: Any) -> str:
    """거래대금(원) → 억원 단위 표기(design/21 §7-1 TOP30 테이블, v2 전용)."""
    if _missing(v):
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

    design/20 Phase 9에서 rmtree를 없앤 이유(동결 모닝 아카이브가 v1 자산을 참조)는 design/25
    (2026-07-29) 아카이브 삭제로 소멸했다. 그래도 삭제 없는 복사를 유지한다 — 소스에서 지운
    자산이 docs에 남는 것은 무해하지만, 빌드가 docs/static을 통째로 지우는 동작은 발행물 사고의
    폭이 크다. 은퇴한 자산(style.css·app.js)은 design/25에서 수동으로 1회 정리했다.
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dst = DOCS_DIR / "static"
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, dst, dirs_exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
