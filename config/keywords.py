"""키워드 사전 단일 홈 — 뉴스 카테고리 + 테마. 계산 로직은 calculators/에서.

매칭 규칙은 calculators/keyword_match.py가 단독으로 정한다: **영문 키워드는 단어 경계**
(+복수형), **한글 키워드는 부분문자열**(교착어). 그래서 영어 합성어를 잡으려면 여기에
표제어로 등록해야 한다 — 정규식으로 접미사를 열면 "chip"이 "chipotle"까지 삼킨다.
"""
from __future__ import annotations

# 뉴스 센터 카테고리(제목/요약 소문자 매칭)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ai": [
        "ai", "인공지능", "gpt", "llm", "chatgpt", "openai", "generative", "생성형",
        "머신러닝", "딥러닝", "nvidia", "엔비디아",
    ],
    "semiconductor": [
        "반도체", "semiconductor", "chip", "chipmaker", "칩", "hbm", "foundry", "파운드리",
        "tsmc", "삼성전자", "sk하이닉스", "하이닉스", "micron", "마이크론", "amd", "asml",
        "웨이퍼",
    ],
    "macro": [
        # "federal reserve"는 "fed"의 단어 경계 밖이라 별도 표제어가 필요하다
        # (실측 400건에서 "federal" 6회 — 경계만 적용하면 통째로 놓친다).
        "금리", "기준금리", "fed", "federal reserve", "연준", "fomc", "inflation", "물가",
        "cpi", "ppi", "gdp", "환율", "유가", "국채", "실업", "고용", "경기", "recession",
        "경기침체",
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
    "반도체": ["반도체", "semiconductor", "chip", "chipmaker", "hbm", "파운드리", "tsmc",
             "엔비디아", "nvidia", "삼성전자", "하이닉스", "micron", "마이크론"],
    "방산": ["방산", "방위", "defense", "무기", "미사일", "한화에어로", "kai"],
    "원전": ["원전", "원자력", "nuclear", "smr"],
    "2차전지": ["2차전지", "배터리", "battery", "양극재", "전고체", "에너지솔루션"],
    "로봇": ["로봇", "robot", "휴머노이드"],
    "바이오": ["바이오", "제약", "신약", "임상", "biotech"],
    "조선": ["조선", "선박", "해운", "shipbuilding", "한화오션", "hd현대"],
    "에너지": ["에너지", "전력", "유가", "태양광", "풍력", "lng", "energy"],
    "금융": ["금융", "은행", "증권", "보험", "금리", "연준", "fed", "federal reserve"],
    "헬스케어": ["헬스케어", "의료", "병원", "healthcare"],
}

# 키워드 레이더(design/03 §3-5) — "많이 언급된 키워드" 카드의 어휘.
#
# THEME_KEYWORDS와 따로 두는 이유: 테마는 **업종 순환**을 보는 11개 큰 덩어리이고(모닝리포트),
# 레이더는 **오늘 무슨 얘기가 오갔나**를 보는 세분 항목이다. FOMC·관세·실적처럼 업종이 아닌
# 이벤트성 화두가 레이더에는 필요하고 테마에는 들어갈 자리가 없다. 둘을 합치면 한쪽이
# 반드시 어색해진다.
#
# 키 = 화면 표시 라벨, 값 = 별칭 목록. 별칭을 묶어야 "nvidia"와 "엔비디아", "fed"와 "연준"이
# 한 행으로 집계된다(영문 기사와 한글 기사가 같은 화두를 다뤄도 따로 세면 순위가 무너진다).
# 매칭 규칙은 calculators/keyword_match.py를 그대로 따른다(영문 단어경계 · 한글 부분문자열).
RADAR_KEYWORDS: dict[str, list[str]] = {
    # ── 거시·정책 ──
    "FOMC": ["fomc", "연방공개시장위원회"],
    "연준": ["fed", "federal reserve", "연준", "파월", "powell"],
    "금리": ["금리", "기준금리", "interest rate", "rate cut", "rate hike"],
    "물가": ["물가", "인플레이션", "inflation"],
    "CPI": ["cpi", "소비자물가"],
    "고용": ["고용", "실업", "일자리", "payroll", "unemployment", "jobless"],
    "GDP": ["gdp", "국내총생산"],
    "환율": ["환율", "원달러", "달러화", "exchange rate"],
    "국채": ["국채", "채권", "treasury", "bond yield", "수익률"],
    "관세": ["관세", "tariff", "무역전쟁", "trade war"],
    "지정학": ["지정학", "전쟁", "제재", "sanction", "geopolitical"],
    # ── 기업·수급 ──
    "실적": ["실적", "어닝", "earnings", "guidance", "가이던스"],
    "IPO": ["ipo", "상장", "공모"],
    "M&A": ["m&a", "인수합병", "인수", "합병", "acquisition", "merger"],
    "배당": ["배당", "dividend"],
    "자사주": ["자사주", "buyback"],
    "공매도": ["공매도", "short selling"],
    # ── 산업 ──
    "AI": ["ai", "인공지능", "생성형", "generative ai"],
    "반도체": ["반도체", "semiconductor", "chip", "chipmaker", "칩"],
    "HBM": ["hbm", "고대역폭"],
    "파운드리": ["파운드리", "foundry"],
    "GPU": ["gpu", "그래픽처리"],
    "2차전지": ["2차전지", "배터리", "battery", "양극재"],
    "전기차": ["전기차", "ev", "electric vehicle"],
    "로봇": ["로봇", "robot", "휴머노이드"],
    "바이오": ["바이오", "제약", "신약", "임상", "biotech"],
    "방산": ["방산", "방위산업", "defense"],
    "원전": ["원전", "원자력", "nuclear", "smr"],
    "조선": ["조선", "선박", "해운", "shipbuilding"],
    "유가": ["유가", "국제유가", "wti", "브렌트", "crude"],
    "비트코인": ["비트코인", "bitcoin", "btc", "가상자산"],
    "부동산": ["부동산", "주택", "housing", "real estate"],
}
