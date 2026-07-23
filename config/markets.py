"""시장 심볼 유니버스 — 모닝리포트 8지표(market.json 필드) 정의."""
from __future__ import annotations

from config.settings import NIGHT_FUTURES_MAX_AGE_WEEKEND_H

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
# STALE 문턱을 3T 일반식(design/00 §9-2)으로 역산해 채운다. 기준은 표시 만료의 **상한**인
# 주말 한도(60h)다 — 평일 한도(20h)로 잡으면 월요일 아침에 정상 표시되는 금요일 밤 세션 값이
# STALE 배지를 달아, 배지가 게시 정책과 어긋나 보인다(design/23 P2).
_NIGHT_FUTURES_EXPECTED_T_MIN = (NIGHT_FUTURES_MAX_AGE_WEEKEND_H // 3) * 60

# Envelope 메타(unit, session_key, expected_T_min, scale) — market.json 심볼별 정의.
# session_key: kr_regular|kr_night|us_regular|globex|fx|crypto_24h|none (schema/envelope.schema.json)
# expected_T_min(분): design/21 §6-2 실측표. scale: 수집값 → 표시값 배율(기본 1.0).
#   ^TNX(미10Y)는 실측 확인 결과 yfinance fast_info.last_price가 이미 정규화된 수익률(%)을
#   그대로 반환한다(예: 4.54 = 4.54%, "수익률×10" 통설과 달리 배율 변환 불필요 — 2026-07-20 실측).
# ── 교차검증(design/23 D) ──────────────────────────────────────────────────────
# Yahoo 값이 맞는지 판단할 근거가 없다는 것이 P4의 본질이었다(값이 틀렸다는 증거도, 맞다는
# 증거도 없었다). FinanceDataReader는 이미 랭킹 수집기가 쓰는 기존 의존성이고 백엔드가
# Yahoo와 다르므로(KRX/네이버 계열) 독립 대조군이 된다 — 신규 의존성 없이 2소스 확보.
# 키 = market.json 필드명, 값 = FinanceDataReader 심볼 코드.
CROSS_CHECK_CODES: dict[str, str] = {
    "sp500": "US500",
    "nasdaq": "IXIC",
    "dow": "DJI",
    "vix": "VIX",
    "kospi": "KS11",
    "kosdaq": "KQ11",
}
# 두 소스 등락률 차가 이 값(%p)을 넘으면 degraded로 표시한다. 실측(2026-07-24) 기준
# 지수는 소수점까지 일치했고 VIX만 0.40%p 벌어졌다(기준 종가 차이) — 0.5%p면 정상 오차는
# 통과시키고 소스 하나가 어긋나는 상황만 잡아낸다.
CROSS_CHECK_TOLERANCE_PP = 0.5

# 등락률 sanity 상한(%). 소스 오류(자릿수 밀림·기준가 오배정)만 걸러내는 것이 목적이라
# **실제로 일어난 적 있는 극단값은 통과**시키도록 넉넉히 잡는다 — 폭락일에 값이 사라지는
# 것이 잘못된 값을 보여주는 것보다 낫다는 보장은 없다(그날이야말로 봐야 하는 날이다).
# 예: 1987 다우 -22.6%, VIX 단일일 +115% 전례.
MAX_ABS_CHANGE_PCT: dict[str, float] = {
    **{k: 25.0 for k in ("kospi", "kosdaq", "sp500", "nasdaq", "dow", "sox", "nq_futures")},
    **{k: 150.0 for k in ("vix", "move")},
    **{k: 10.0 for k in ("usdkrw", "usdjpy", "eurusd", "usdcny", "dxy")},
    **{k: 40.0 for k in ("wti", "gold", "copper", "natgas")},
    "btc": 50.0,
    "us10y": 30.0,
}
MAX_ABS_CHANGE_PCT_DEFAULT = 50.0

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
