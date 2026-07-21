"""키워드 사전 단일 홈 — 뉴스 카테고리 + 테마. 계산 로직은 calculators/에서."""
from __future__ import annotations

# 뉴스 센터 카테고리(제목/요약 소문자 매칭)
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

# 카테고리 표시 순서/라벨(뉴스 센터)
CATEGORY_ORDER: list[tuple[str, str]] = [
    ("breaking", "속보"),
    ("kr_market", "한국 증시"),
    ("us_market", "미국 증시"),
    ("ai", "AI"),
    ("semiconductor", "반도체"),
    ("macro", "매크로"),
]

# 주목 테마(모닝리포트) — 수집 뉴스 빈도로만 산출, 수기 지정 금지
THEME_KEYWORDS: dict[str, list[str]] = {
    "AI": ["ai", "인공지능", "gpt", "llm", "생성형", "openai", "챗gpt"],
    "반도체": ["반도체", "semiconductor", "chip", "hbm", "파운드리", "tsmc", "엔비디아", "nvidia",
             "삼성전자", "하이닉스", "micron", "마이크론"],
    "방산": ["방산", "방위", "defense", "무기", "미사일", "한화에어로", "kai"],
    "원전": ["원전", "원자력", "nuclear", "smr"],
    "2차전지": ["2차전지", "배터리", "battery", "양극재", "전고체", "에너지솔루션"],
    "로봇": ["로봇", "robot", "휴머노이드"],
    "바이오": ["바이오", "제약", "신약", "임상", "biotech"],
    "조선": ["조선", "선박", "해운", "shipbuilding", "한화오션", "hd현대"],
    "에너지": ["에너지", "전력", "유가", "태양광", "풍력", "lng", "energy"],
    "금융": ["금융", "은행", "증권", "보험", "금리", "연준", "fed"],
    "헬스케어": ["헬스케어", "의료", "병원", "healthcare"],
}
