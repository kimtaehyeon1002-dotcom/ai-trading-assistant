"""시장 유니버스 — 워치리스트/지수/선물/환율(yfinance 심볼). 자유롭게 편집."""
from __future__ import annotations

# 워치리스트 (yfinance 심볼, 표시명)
WATCHLIST: dict[str, list[tuple[str, str]]] = {
    "KR": [
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
        ("373220.KS", "LG에너지솔루션"),
        ("035420.KS", "NAVER"),
        ("035720.KS", "카카오"),
        ("005380.KS", "현대차"),
    ],
    "US": [
        ("AAPL", "Apple"),
        ("NVDA", "Nvidia"),
        ("MSFT", "Microsoft"),
        ("TSLA", "Tesla"),
        ("AMD", "AMD"),
        ("TSM", "TSMC"),
    ],
}

# 주요 지수
INDICES: list[tuple[str, str]] = [
    ("^KS11", "KOSPI"),
    ("^KQ11", "KOSDAQ"),
    ("^GSPC", "S&P 500"),
    ("^IXIC", "NASDAQ"),
    ("^DJI", "Dow Jones"),
]

# 선물
FUTURES: list[tuple[str, str]] = [
    ("ES=F", "S&P500 선물"),
    ("NQ=F", "NASDAQ 선물"),
    ("YM=F", "Dow 선물"),
    ("CL=F", "WTI 원유"),
    ("GC=F", "금"),
]

# 환율 (base, quote)
FX_PAIRS: list[tuple[str, str]] = [
    ("USD", "KRW"),
    ("USD", "JPY"),
    ("EUR", "USD"),
]
