"""사이드바·헤더 메뉴 단일 소스(design/22 §4-2).

v2 셸(base_v2.html·nav.html 매크로)이 이 목록을 소비한다. v1 셸(templates/base.html)은
Phase 9까지 동결 대상이라 이 시점에는 여전히 하드코딩 5링크를 그대로 유지하며 이 모듈을
소비하지 않는다 — "동결"과 "nav 단일 소스 신설"은 서로 다른 시점의 작업이다(design/20 Phase 1·9).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str  # active 매칭 키
    label: str
    href: str  # root 기준 상대경로(예: "/index.html")
    icon: str = ""  # 20x20 아이콘 식별자(스프라이트/이모지 등은 구현 시 결정)
    locked: bool = False  # True면 사이드바에 자물쇠 표기(Asset/Portfolio)


# 상단 일반 메뉴 6개 + 디바이더 + 잠금 그룹 2개 (design/00 §6-1)
MAIN_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Dashboard", "/index.html"),
    NavItem("macro", "Macroeconomics", "/macro/index.html"),
    NavItem("news", "News", "/news/index.html"),
    NavItem("stock", "Stock", "/stock/index.html"),
    NavItem("financials", "Financial Statements", "/financials/index.html"),
    NavItem("ta", "Technical Analysis", "/ta/index.html"),
)
LOCKED_ITEMS: tuple[NavItem, ...] = (
    NavItem("asset", "Asset", "/asset/index.html", locked=True),
    NavItem("portfolio", "Portfolio", "/portfolio/index.html", locked=True),
)

# 하단 영역(design/00 §6-5)
SETTINGS_ITEM = NavItem("settings", "Settings", "/settings/index.html")


def context(active: str) -> dict:
    """base_v2/nav.html 렌더에 그대로 주입하는 컨텍스트. active와 일치하는 항목만 표시측이 강조."""
    return {
        "active": active,
        "main_items": MAIN_ITEMS,
        "locked_items": LOCKED_ITEMS,
        "settings_item": SETTINGS_ITEM,
    }
