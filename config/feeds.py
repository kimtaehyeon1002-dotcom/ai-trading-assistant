"""뉴스 소스(RSS) + 카테고리 키워드. 저작권 안전: 제목+요약+링크만 사용, 본문 미저장.

카테고리는 소스 지역(KR/US)과 제목/요약 키워드로 분류(kr_market/us_market/ai/semiconductor/macro/breaking).
피드 일부가 실패해도 나머지로 계속 진행한다(수집기에서 개별 예외 격리).
"""
from __future__ import annotations

# 공개 RSS (헤드라인+링크). source/region/lang 메타 부착.
SOURCES: list[dict] = [
    {"url": "https://www.hankyung.com/feed/finance", "source": "한국경제", "region": "KR", "lang": "ko"},
    {"url": "https://www.mk.co.kr/rss/30100041/", "source": "매일경제·증권", "region": "KR", "lang": "ko"},
    {"url": "https://www.yna.co.kr/rss/economy.xml", "source": "연합뉴스·경제", "region": "KR", "lang": "ko"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "source": "WSJ Markets", "region": "US", "lang": "en"},
    {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "source": "MarketWatch", "region": "US", "lang": "en"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC Finance", "region": "US", "lang": "en"},
]

# 카테고리 키워드(제목/요약 소문자 매칭). 다중 매칭 가능.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ai": [
        "ai", "인공지능", "gpt", "llm", "chatgpt", "openai", "generative", "생성형",
        "머신러닝", "딥러닝", "nvidia", "엔비디아",
    ],
    "semiconductor": [
        "반도체", "semiconductor", "chip", "칩", "hbm", "foundry", "파운드리", "tsmc",
        "삼성전자", "sk하이닉스", "하이닉스", "micron", "마이크론", "amd", "asml", "웨이퍼",
    ],
    "macro": [
        "금리", "기준금리", "fed", "연준", "fomc", "inflation", "물가", "cpi", "ppi",
        "gdp", "환율", "유가", "국채", "실업", "고용", "경기", "recession", "경기침체",
    ],
}

# 카테고리 표시 순서/라벨
CATEGORY_ORDER: list[tuple[str, str]] = [
    ("breaking", "속보"),
    ("kr_market", "한국 증시"),
    ("us_market", "미국 증시"),
    ("ai", "AI"),
    ("semiconductor", "반도체"),
    ("macro", "매크로"),
]
