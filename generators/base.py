"""Jinja2 환경 + 렌더/정적복사 유틸. 모든 생성기가 공유."""
from __future__ import annotations

import hashlib
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


_asset_version: str | None = None


def asset_v() -> str:
    """static/ 전체 내용의 짧은 해시 — 자산 URL의 `?v=` 값.

    왜 필요한가: GitHub Pages는 JS/CSS에 `Cache-Control: max-age=600`을 붙인다. HTML은
    매 빌드 갱신되는데 자산은 최대 10분간 옛것이 쓰이므로, **새 HTML + 캐시된 옛 JS** 조합이
    생긴다. 마크업과 스크립트 사이에 계약이 있으면(예: Macro 라이브 피드의 data-live-* 속성)
    그 조합에서 기능이 조용히 죽는다 — 에러도 안 나서 알아채기까지 오래 걸린다.

    타임스탬프가 아니라 **내용 해시**인 이유: 시각으로 버스팅하면 자산이 그대로인 매시 빌드마다
    전 사용자가 재다운로드한다. 내용이 바뀔 때만 값이 바뀌어야 캐시가 제 일을 한다.

    빌드 1회당 한 번만 계산한다(모듈 캐시). 자산이 수십 KB라 비용은 무시할 수준이다.
    """
    global _asset_version
    if _asset_version is None:
        h = hashlib.sha1()
        if STATIC_DIR.exists():
            for path in sorted(STATIC_DIR.rglob("*")):
                if path.is_file():
                    h.update(path.relative_to(STATIC_DIR).as_posix().encode("utf-8"))
                    h.update(path.read_bytes())
        _asset_version = h.hexdigest()[:8]
    return _asset_version


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.globals["site"] = SITE
_env.globals["asset_v"] = asset_v
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
