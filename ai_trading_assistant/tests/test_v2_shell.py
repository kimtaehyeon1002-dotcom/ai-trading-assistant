"""Phase 1 공존 셸 + 토큰 최소본 — DoD 검증(design/20 Phase 1)."""
from __future__ import annotations

import re
from pathlib import Path

from config import nav
from config.settings import ensure_dirs, TEMPLATES_DIR
from generators import registry
from generators.skeleton_v2 import generate as gen_v2_skeleton

ROOT = Path(__file__).resolve().parent.parent
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,6}\b")


def _hex_matches(text: str) -> list[str]:
    return HEX_RE.findall(text)


def test_tokens_css_hex_confined_to_primitives_block():
    """primitives 블록 밖에는 hex 리터럴이 없어야 한다(R6 린트, design/00 §2-6·design/20 Phase 1 DoD)."""
    text = (ROOT / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    start = text.index("PRIMITIVES (private)")
    end = text.index("END PRIMITIVES")
    before, primitives, after = text[:start], text[start:end], text[end:]
    assert _hex_matches(primitives), "primitives 블록에는 실제 hex 값이 있어야 한다"
    assert _hex_matches(before) == []
    assert _hex_matches(after) == []


def test_v2_css_and_html_have_zero_hex():
    targets = [
        ROOT / "static" / "css" / "base_v2.css",
        ROOT / "static" / "css" / "components.css",
        ROOT / "templates" / "base_v2.html",
        ROOT / "templates" / "_macros_v2" / "nav.html",
        ROOT / "templates" / "_macros_v2" / "card.html",
        ROOT / "templates" / "pages" / "skeleton_v2.html",
        ROOT / "templates" / "pages" / "ta.html",
        ROOT / "templates" / "pages" / "dashboard_v2.html",
        ROOT / "templates" / "pages" / "news_v2.html",
        ROOT / "templates" / "_macros_v2" / "news.html",
        ROOT / "templates" / "pages" / "macro.html",
        ROOT / "templates" / "pages" / "stock.html",
        ROOT / "templates" / "_macros_v2" / "stock.html",
        ROOT / "templates" / "pages" / "financials.html",
        ROOT / "templates" / "pages" / "trades_v2.html",
        ROOT / "templates" / "pages" / "asset.html",
        ROOT / "templates" / "pages" / "portfolio.html",
        ROOT / "templates" / "_macros_v2" / "gate.html",
        ROOT / "templates" / "pages" / "settings.html",
        ROOT / "templates" / "pages" / "ai_office_v2.html",
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert _hex_matches(text) == [], f"{path.name}에 hex 리터럴 존재: {_hex_matches(text)}"


def test_registry_all_targets_preserves_original_order_and_set():
    """build.py 레지스트리 재설계가 기존 'all' 페이지 구성(morning→news→trades)을 그대로 보존하고,
    이후 무비용 클라이언트 전용 페이지(settings, design/20 Phase 9)만 추가됐는지 확인한다."""
    assert registry.ALL_TARGETS == ("morning", "news", "trades", "settings")


def test_v2preview_not_in_registry_all():
    assert "v2preview" not in registry.ALL_TARGETS
    assert "v2preview" in registry.TARGETS


def test_build_targets_include_original_five_plus_v2preview():
    import build

    for original in ("morning", "news", "trades", "dashboard", "all"):
        assert original in build.TARGETS
    assert "v2preview" in build.TARGETS


def test_v2_skeleton_not_exposed_in_nav_items():
    """스켈레톤 라우트의 active 키가 실제 nav 항목 어디와도 일치하지 않는다(nav 미노출 계약)."""
    ctx = nav.context(active="__v2_preview__")
    keys = [i.key for i in ctx["main_items"]] + [i.key for i in ctx["locked_items"]] + [ctx["settings_item"].key]
    assert "__v2_preview__" not in keys


def test_v2_skeleton_page_renders_shell():
    ensure_dirs()
    out = gen_v2_skeleton()
    html = out.read_text(encoding="utf-8")
    assert 'class="v2-sidebar"' in html
    assert 'class="v2-header"' in html
    assert 'class="v2-panel-slot"' in html
    assert "tokens.css" in html
    assert "base_v2.css" in html
    assert 'data-updown="kr"' in html
    # 헤더 컨텍스트가 nav에 없는 페이지를 위해 잘못된 라벨("Settings" 등)로 대체되지 않아야 한다
    assert "Settings\n  </div>" not in html


def test_templates_dir_has_v2_shell_files():
    assert (TEMPLATES_DIR / "base_v2.html").exists()
    assert (TEMPLATES_DIR / "_macros_v2" / "nav.html").exists()
