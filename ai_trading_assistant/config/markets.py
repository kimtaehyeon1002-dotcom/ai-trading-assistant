"""시장 심볼 유니버스 — 모닝리포트 8지표(market.json 필드) 정의."""
from __future__ import annotations

from config.settings import NIGHT_FUTURES_MAX_AGE_H

# 미국시장(키 = market.json 필드명) — Yahoo Finance
MORNING_US_INDICES: list[tuple[str, str, str]] = [
    ("nasdaq", "^IXIC", "NASDAQ"),
    ("sp500", "^GSPC", "S&P500"),
    ("dow", "^DJI", "DOW"),
    ("sox", "^SOX", "필라델피아 반도체"),
]

WTI_SYMBOL = "CL=F"  # Yahoo Finance

TA_KOSPI_SYMBOL = "^KS11"  # Technical Analysis 프리뷰용(design/21 §2-7)

# 시세 유니버스 증분 확장(design/20 Phase 3) — 신규 수집기 없이 Yahoo만으로 채울 수 있는 심볼.
# 키 = market.json 필드명, 심볼 = Yahoo Finance 티커, 라벨 = 표시명.
EXTENDED_SYMBOLS: list[tuple[str, str, str]] = [
    ("kospi", "^KS11", "KOSPI"),
    ("kosdaq", "^KQ11", "KOSDAQ"),
    ("vix", "^VIX", "VIX"),
    ("move", "^MOVE", "ICE BofA MOVE"),
    ("dxy", "DX-Y.NYB", "달러인덱스"),
    ("gold", "GC=F", "금"),
    ("copper", "HG=F", "구리"),
    ("natgas", "NG=F", "천연가스"),
    ("nq_futures", "NQ=F", "나스닥100 선물"),
    ("us10y", "^TNX", "미국 10년물 국채금리"),
    ("usdjpy", "JPY=X", "USD/JPY"),
    ("eurusd", "EURUSD=X", "EUR/USD"),
    ("usdcny", "CNY=X", "USD/CNY"),
    ("btc", "BTC-USD", "비트코인"),
]

# 야간선물 expected_T_min — 자동 FRESH/DELAYED 판정 미지원(design/21 §6-2 "(자동 미지원)")이므로
# STALE 문턱(NIGHT_FUTURES_MAX_AGE_H, 현행 60h)을 3T 일반식(design/00 §9-2)으로 역산해 채운다.
_NIGHT_FUTURES_EXPECTED_T_MIN = (NIGHT_FUTURES_MAX_AGE_H // 3) * 60

# Envelope 메타(unit, session_key, expected_T_min, scale) — market.json 심볼별 정의.
# session_key: kr_regular|kr_night|us_regular|globex|fx|crypto_24h|none (schema/envelope.schema.json)
# expected_T_min(분): design/21 §6-2 실측표. scale: 수집값 → 표시값 배율(기본 1.0).
#   ^TNX(미10Y)는 실측 확인 결과 yfinance fast_info.last_price가 이미 정규화된 수익률(%)을
#   그대로 반환한다(예: 4.54 = 4.54%, "수익률×10" 통설과 달리 배율 변환 불필요 — 2026-07-20 실측).
ENVELOPE_META: dict[str, tuple[str, str, int, float]] = {
    "kospi_night": ("pt", "kr_night", _NIGHT_FUTURES_EXPECTED_T_MIN, 1.0),
    "kosdaq_night": ("pt", "kr_night", _NIGHT_FUTURES_EXPECTED_T_MIN, 1.0),
    "usdkrw": ("KRW", "fx", 1440, 1.0),
    "wti": ("USD", "globex", 30, 1.0),
    "nasdaq": ("pt", "us_regular", 30, 1.0),
    "sp500": ("pt", "us_regular", 30, 1.0),
    "dow": ("pt", "us_regular", 30, 1.0),
    "sox": ("pt", "us_regular", 30, 1.0),
    "kospi": ("pt", "kr_regular", 30, 1.0),
    "kosdaq": ("pt", "kr_regular", 30, 1.0),
    "vix": ("pt", "us_regular", 30, 1.0),
    "move": ("pt", "us_regular", 30, 1.0),
    "dxy": ("pt", "globex", 30, 1.0),
    "gold": ("USD", "globex", 30, 1.0),
    "copper": ("USD", "globex", 30, 1.0),
    "natgas": ("USD", "globex", 30, 1.0),
    "nq_futures": ("pt", "globex", 30, 1.0),
    "us10y": ("%", "us_regular", 30, 1.0),
    "usdjpy": ("JPY", "fx", 30, 1.0),
    "eurusd": ("USD", "fx", 30, 1.0),
    "usdcny": ("CNY", "fx", 30, 1.0),
    "btc": ("USD", "crypto_24h", 30, 1.0),
}
