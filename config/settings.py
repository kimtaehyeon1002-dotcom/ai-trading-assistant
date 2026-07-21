"""전역 설정 — 경로/사이트/타임존/분류 기준/API 키. 비즈니스 로직 금지."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# ── 경로 ──
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"        # GitHub Pages (읽기 전용 발행물)
CACHE_DIR = BASE_DIR / "cache"      # 자동 수집 데이터(JSON, 재생성 가능·미커밋)
DATA_DIR = BASE_DIR / "data"        # 커밋되는 원장(매매 이력)
TRADES_DIR = DATA_DIR / "trades"
DATA_CACHE_DIR = DATA_DIR / "cache"  # 데스크톱→CI 전달 캐시(커밋됨; 예: 야간선물)
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
VAULT_DIR = BASE_DIR / "vault"       # Obsidian vault(커밋됨) — 워치리스트/장기기억
VAULT_WATCHLIST_DIR = VAULT_DIR / "00_Watchlist"

# ── 타임존 ──
TIMEZONE = ZoneInfo(os.getenv("TZ_NAME", "Asia/Seoul"))

# ── 사이트 메타 ──
SITE = {
    "title": os.getenv("SITE_TITLE", "AI Trading Assistant"),
    "author": os.getenv("SITE_AUTHOR", "kimtaehyeon"),
    "base_url": os.getenv("SITE_BASE_URL", ""),
}

# ── 매매 분류 기준(보유일수): day ≤ 0 < swing ≤ 20 < long ──
CLASSIFY = {
    "day_max_days": int(os.getenv("CLASSIFY_DAY_MAX", "0")),
    "swing_max_days": int(os.getenv("CLASSIFY_SWING_MAX", "20")),
}

# ── 수집/렌더 상한 ──
NEWS_MAX_PER_CATEGORY = int(os.getenv("NEWS_MAX_PER_CATEGORY", "20"))
NEWS_FETCH_LIMIT = int(os.getenv("NEWS_FETCH_LIMIT", "40"))
BREAKING_WINDOW_MIN = int(os.getenv("BREAKING_WINDOW_MIN", "90"))
# 야간선물 신선도 한도 — 주말 갭 필수 고려: 금요일 밤 세션 데이터가 월요일 06:30 리포트에
# 나와야 하므로 24h면 부족(일요일 새벽 동기화도 월 06:30에 28.8h로 만료됨). 60h = 금 22시
# 동기화(56.5h) 커버, 그 이상 낡은 값은 생략.
NIGHT_FUTURES_MAX_AGE_H = int(os.getenv("NIGHT_FUTURES_MAX_AGE_H", "60"))


def ensure_dirs() -> None:
    for d in (DOCS_DIR, CACHE_DIR, TRADES_DIR, DATA_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
