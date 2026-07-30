"""전역 설정 — 경로/사이트/타임존/분류 기준/API 키. 비즈니스 로직 금지."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv(path: Path) -> None:
    """`.env`(gitignored) → os.environ. 이미 설정된 환경변수가 항상 우선한다.

    자산 4계좌 수집이 데스크톱 전용이 되면서(design/21 §281) KIS·Bybit 자격증명과
    ASSET_PASSPHRASE를 로컬에 둘 자리가 필요해졌다. 외부 의존성(python-dotenv)을 더하지
    않고 KEY=VALUE 한 줄 파싱만 한다 — 값에 '#'이 들어갈 수 있으므로 주석 제거는 줄 첫
    글자 기준으로만 판단하고, 감싼 따옴표만 벗긴다.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
# 실행당 신규 번역 상한(design/24 Phase A 확장) — 무료 비공식 번역 엔드포인트라 요청이 많으면
# 느려지거나 차단될 수 있다. 상한을 두어 한 번의 빌드가 오래 걸리지 않게 하고, 못 채운 나머지는
# 다음 실행(뉴스 cron 30분 간격)이 이어받는다(이미 번역된 기사는 재번역하지 않으므로 손실 없음).
# 80으로 상향: 번역 결과가 data/cache/news_translations.json에 누적되기 전에는 매 실행이
# "최신 40건"만 번역하고 끝나 오래된 영어 기사가 영원히 남았다. 캐시가 생겨 재번역이 사라진
# 지금은 상한이 곧 "밀린 backlog를 얼마나 빨리 따라잡는가"만 결정한다(1건당 2회 호출·~1.4초).
NEWS_MAX_TRANSLATE_PER_RUN = int(os.getenv("NEWS_MAX_TRANSLATE_PER_RUN", "80"))
# 야간선물 표시 만료 — 평일/주말 이원화(design/23 P2).
# 종전에는 평일에도 60h를 적용해, 이틀 전 야간 세션 값이 "오늘 새벽 시세"인 양 대시보드에
# 남는 결함이 있었다(실제 사고: 07-22 23:12 값 -0.06%가 07-24 06:04 리포트까지 생존).
#   평일 20h — 정상 경로를 모두 덮는 최소치: 세션 개시(18:00) 직후 수집분이 다음 날 06:30
#              리포트에 실릴 때가 12.5h로 최장이다. 반대로 '어제 새벽' 값(≥25.8h)은 확실히
#              탈락시킨다(한 세션 낡은 값 차단이 이 문턱의 존재 이유).
#   주말 60h — 금요일 밤 세션(토 05:00 마감) 값이 월요일 06:30 리포트에 실려야 한다.
#              금 22:30 수집분 기준 56h → 60h. 이 한도는 구간에 토·일이 낀 경우에만 적용된다.
# 공휴일 연휴는 등재된 holidays가 없어 커버하지 않는다 — 낡은 값을 보여주느니 빈칸이 낫다.
NIGHT_FUTURES_MAX_AGE_H = int(os.getenv("NIGHT_FUTURES_MAX_AGE_H", "20"))
NIGHT_FUTURES_MAX_AGE_WEEKEND_H = int(os.getenv("NIGHT_FUTURES_MAX_AGE_WEEKEND_H", "60"))

# ── 거시경제(design/20 Phase 6) — 무료 키 발급 필요, 미설정 시 해당 수집기 skipped ──
FRED_API_KEY = os.getenv("FRED_API_KEY", "")  # https://fred.stlouisfed.org (Federal Reserve)
ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")  # https://ecos.bok.or.kr (한국은행)

# ── Financial Statements(design/20 Phase 7) — DART는 무료 키 발급 필요(미설정 시 KR 결측,
# design/21 §226과 동일한 결측 문법). EDGAR는 키 불필요(User-Agent 헤더만 요구) ──
DART_API_KEY = os.getenv("DART_API_KEY", "")  # https://opendart.fss.or.kr
EDGAR_USER_AGENT = os.getenv("EDGAR_USER_AGENT", "AI-Trading-Assistant contact@example.com")

# ── Asset/Portfolio 4계좌 자동 수집(design/20 Phase 8) — 미설정 시 결측(가짜 데이터 금지) ──
# 한국투자(KIS) — 위탁(미국주식)·ISA(ETF)를 **계좌마다 별도 앱키**로 조회한다.
# 원래는 "앱키 1개 + 계좌번호만 분리"를 가정했으나, 실키 검증(2026-07-26)에서 위탁 앱키로 ISA
# 계좌를 조회하면 상품코드를 무엇으로 바꿔도 INVALID_CHECK_ACNO로 거부됐다 — KIS 앱키는 발급 시
# 연결한 계좌에만 유효하다. 그래서 계좌별 자격증명을 따로 받는다.
# ISA 전용 키가 비어 있으면 공용(KIS_APP_KEY)으로 폴백한다 — 두 계좌가 한 앱키에 묶인 사용자도
# 설정 변경 없이 그대로 동작하게 하기 위한 하위 호환이다.
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_FOREIGN = os.getenv("KIS_ACCOUNT_FOREIGN", "")  # 위탁(미국주식) 계좌번호
KIS_ACCOUNT_ISA = os.getenv("KIS_ACCOUNT_ISA", "")  # ISA(ETF) 계좌번호
KIS_ISA_APP_KEY = os.getenv("KIS_ISA_APP_KEY", "")  # 비우면 KIS_APP_KEY로 폴백
KIS_ISA_APP_SECRET = os.getenv("KIS_ISA_APP_SECRET", "")
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
