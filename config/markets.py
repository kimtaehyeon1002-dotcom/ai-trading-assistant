"""시장 심볼 유니버스 — 모닝리포트 8지표(market.json 필드) 정의."""
from __future__ import annotations

# 미국시장(키 = market.json 필드명) — Yahoo Finance
MORNING_US_INDICES: list[tuple[str, str, str]] = [
    ("nasdaq", "^IXIC", "NASDAQ"),
    ("sp500", "^GSPC", "S&P500"),
    ("dow", "^DJI", "DOW"),
    ("sox", "^SOX", "필라델피아 반도체"),
]

WTI_SYMBOL = "CL=F"  # Yahoo Finance
