"""전역 설정 — 경로, 사이트 메타, 타임존, 분류 기준. 환경변수로 일부 오버라이드 가능."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"  # GitHub Pages 산출물
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
TRADES_DIR = DATA_DIR / "trades"
REPORTS_DIR = DATA_DIR / "reports"
CACHE_DIR = DATA_DIR / "cache"

# ── 타임존 ──
TIMEZONE = ZoneInfo(os.getenv("TZ_NAME", "Asia/Seoul"))

# ── 사이트 메타 ──
SITE = {
    "title": os.getenv("SITE_TITLE", "AI Trading Assistant"),
    "author": os.getenv("SITE_AUTHOR", "kimtaehyeon"),
    # GitHub Pages 배포 URL (예: https://user.github.io/repo). 상대경로 자산이라 비워둬도 동작.
    "base_url": os.getenv("SITE_BASE_URL", ""),
}

# ── 매매 분류 기준(보유일수) ──
# day: 보유 <= day_max_days(당일), swing: <= swing_max_days, long: 초과
CLASSIFY = {
    "day_max_days": int(os.getenv("CLASSIFY_DAY_MAX", "0")),
    "swing_max_days": int(os.getenv("CLASSIFY_SWING_MAX", "20")),
}

# ── 렌더 상한 ──
NEWS_MAX_PER_CATEGORY = int(os.getenv("NEWS_MAX_PER_CATEGORY", "20"))
NEWS_FETCH_LIMIT = int(os.getenv("NEWS_FETCH_LIMIT", "40"))  # 피드당 수집 상한
BREAKING_WINDOW_MIN = int(os.getenv("BREAKING_WINDOW_MIN", "90"))  # 속보 판정(분)


def ensure_dirs() -> None:
    for d in (DOCS_DIR, DATA_DIR, TRADES_DIR, REPORTS_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
