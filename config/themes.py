"""테마 → 종목 수동 매핑(design/21 §7-1 "테마 자금흐름 스트립").

전종목 자동 테마 분류는 오탐이 크므로(config/entities.py와 동일 원칙) 시총 상위 위주로
수기 큐레이션한다. 값의 각 항목 = (티커, 표시명, 시장).
"""
from __future__ import annotations

Ticker = tuple[str, str, str]

THEMES: dict[str, list[Ticker]] = {
    "반도체": [
        ("005930", "삼성전자", "KRX"),
        ("000660", "SK하이닉스", "KRX"),
        ("NVDA", "NVIDIA", "NASDAQ"),
        ("AMD", "AMD", "NASDAQ"),
        ("TSM", "TSMC", "NYSE"),
    ],
    "2차전지": [
        ("373220", "LG에너지솔루션", "KRX"),
        ("006400", "삼성SDI", "KRX"),
        ("247540", "에코프로비엠", "KRX"),
        ("TSLA", "Tesla", "NASDAQ"),
    ],
    "인공지능": [
        ("035420", "NAVER", "KRX"),
        ("035720", "카카오", "KRX"),
        ("MSFT", "Microsoft", "NASDAQ"),
        ("GOOGL", "Alphabet", "NASDAQ"),
        ("META", "Meta", "NASDAQ"),
    ],
    "바이오": [
        ("207940", "삼성바이오로직스", "KRX"),
        ("068270", "셀트리온", "KRX"),
        ("LLY", "Eli Lilly", "NYSE"),
        ("NVO", "Novo Nordisk", "NYSE"),
    ],
    "자동차": [
        ("005380", "현대차", "KRX"),
        ("000270", "기아", "KRX"),
        ("TSLA", "Tesla", "NASDAQ"),
    ],
    "금융": [
        ("055550", "신한지주", "KRX"),
        ("105560", "KB금융", "KRX"),
        ("JPM", "JPMorgan Chase", "NYSE"),
        ("BAC", "Bank of America", "NYSE"),
    ],
}
