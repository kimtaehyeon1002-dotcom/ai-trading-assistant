"""전역 설정 — 경로/사이트/타임존/분류 기준/API 키. 비즈니스 로직 금지."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# ── 경로 ──
# 발행 채널 정책(design/21 §7): docs/**=재조회 가능한 클라이언트 fetch 대상(누적 저장소 금지,
# 담당 워크플로 주기로 재조회). data/**=소급 불가 히스토리 원장만(최소 필드 append). 자산 평문
# 스냅샷은 어느 쪽에도 커밋하지 않는다 — 로컬 전용(.gitignore), design/21 §9-4가 단일 진실.
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"        # GitHub Pages (읽기 전용 발행물)
CACHE_DIR = BASE_DIR / "cache"      # 자동 수집 데이터(JSON, 재생성 가능·미커밋)
DATA_DIR = BASE_DIR / "data"        # 커밋되는 원장(매매 이력)
TRADES_DIR = DATA_DIR / "trades"
DATA_CACHE_DIR = DATA_DIR / "cache"  # 데스크톱→CI 전달 캐시(커밋됨; 예: 야간선물)
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
# Obsidian vault = 별도 저장소 TH_DATA. 로컬=형제 폴더(../TH_DATA), CI=듀얼 checkout 후
# TH_DATA_DIR 환경변수로 주입. 폴더 없으면 수집/write-back 모두 skipped(가짜 데이터 금지).
VAULT_DIR = Path(os.getenv("TH_DATA_DIR") or (BASE_DIR.parent / "TH_DATA"))
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

# ── 거시경제(design/20 Phase 6) — 무료 키 발급 필요, 미설정 시 해당 수집기 skipped ──
FRED_API_KEY = os.getenv("FRED_API_KEY", "")  # https://fred.stlouisfed.org (Federal Reserve)
ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")  # https://ecos.bok.or.kr (한국은행)

# ── Financial Statements(design/20 Phase 7) — DART는 무료 키 발급 필요(미설정 시 KR 결측,
# design/21 §226과 동일한 결측 문법). EDGAR는 키 불필요(User-Agent 헤더만 요구) ──
DART_API_KEY = os.getenv("DART_API_KEY", "")  # https://opendart.fss.or.kr
EDGAR_USER_AGENT = os.getenv("EDGAR_USER_AGENT", "AI-Trading-Assistant contact@example.com")

# ── Asset/Portfolio 4계좌 자동 수집(design/20 Phase 8) — 미설정 시 결측(가짜 데이터 금지) ──
# 한국투자(KIS) — 위탁(미국주식 전용) + ISA(ETF)는 계좌번호만 다르고 API는 공유
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_FOREIGN = os.getenv("KIS_ACCOUNT_FOREIGN", "")  # 위탁(미국주식) 계좌번호
KIS_ACCOUNT_ISA = os.getenv("KIS_ACCOUNT_ISA", "")  # ISA(ETF) 계좌번호
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# 자산 암호화 passphrase(design/20 Phase 8 A안) — 미설정 시 Asset/Portfolio 발행 자체를 skip한다
# (암호화 못 할 데이터를 평문으로 내보내느니 아예 발행하지 않는 것이 안전, §DoD 1의 연장 원칙).
ASSET_PASSPHRASE = os.getenv("ASSET_PASSPHRASE", "")
# 연간 목표 금액(design/08 §3-3) — 개인 목표라 코드에 하드코딩하지 않고 환경변수로 받는다.
# 미설정(0)이면 목표 달성률 카드를 생략한다(결측 문법).
ASSET_GOAL_KRW = float(os.getenv("ASSET_GOAL_KRW", "0") or 0)

# Notion 연동은 Obsidian vault(TH_DATA)로 이관 완료 — 관련 설정은 제거됐다.
# (1회성 이관 스크립트 migrate_notion_watchlist.py는 환경변수를 직접 읽는다.)


def ensure_dirs() -> None:
    for d in (DOCS_DIR, CACHE_DIR, TRADES_DIR, DATA_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
