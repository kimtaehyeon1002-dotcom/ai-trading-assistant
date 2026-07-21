"""종목명 → 티커 사전 — 뉴스 관련종목 태깅용 최소 큐레이션(design/20 Phase 5, design/21 §3).

전종목 매칭은 오탐이 크므로(design/21 §3 "전종목 매칭 오탐 큼") 시총 상위만 수기 큐레이션한다.
키는 제목·요약 소문자 매칭에 쓰이는 이름(중복 별칭 포함), 값은 (티커, 표시명, 시장).
"""
from __future__ import annotations

ENTITIES: dict[str, tuple[str, str, str]] = {
    "삼성전자": ("005930", "삼성전자", "KRX"),
    "sk하이닉스": ("000660", "SK하이닉스", "KRX"),
    "하이닉스": ("000660", "SK하이닉스", "KRX"),
    "네이버": ("035420", "NAVER", "KRX"),
    "카카오": ("035720", "카카오", "KRX"),
    "현대차": ("005380", "현대차", "KRX"),
    "lg에너지솔루션": ("373220", "LG에너지솔루션", "KRX"),
    "포스코홀딩스": ("005490", "POSCO홀딩스", "KRX"),
    "nvidia": ("NVDA", "NVIDIA", "NASDAQ"),
    "엔비디아": ("NVDA", "NVIDIA", "NASDAQ"),
    "apple": ("AAPL", "Apple", "NASDAQ"),
    "애플": ("AAPL", "Apple", "NASDAQ"),
    "microsoft": ("MSFT", "Microsoft", "NASDAQ"),
    "tesla": ("TSLA", "Tesla", "NASDAQ"),
    "테슬라": ("TSLA", "Tesla", "NASDAQ"),
    "amd": ("AMD", "AMD", "NASDAQ"),
    "tsmc": ("TSM", "TSMC", "NYSE"),
    "amazon": ("AMZN", "Amazon", "NASDAQ"),
    "google": ("GOOGL", "Alphabet", "NASDAQ"),
    "meta": ("META", "Meta", "NASDAQ"),
}
