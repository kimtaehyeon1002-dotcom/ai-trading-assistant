"""종목명 → 티커 사전 — 뉴스 관련종목 태깅용 최소 큐레이션(design/20 Phase 5, design/21 §3).

전종목 매칭은 오탐이 크므로(design/21 §3 "전종목 매칭 오탐 큼") 시총 상위만 수기 큐레이션한다.
키는 제목·요약 소문자 매칭에 쓰이는 이름(중복 별칭 포함), 값은 (티커, 표시명, 시장).

매칭 규칙은 calculators/keyword_match.py가 정한다: **영문은 단어 경계**(+복수형),
**한글은 부분문자열**(교착어). 그래서 짧거나 흔한 단어와 겹치는 이름은 등재하지 않는다 —
아래 §주의 참조.

### 한 종목에 한·영 표기를 **둘 다** 넣는 이유
수집원의 절반이 영문 매체다. "삼성전자"만 등재하면 "Samsung Electronics"라고 쓰는 기사는
영영 못 잡는다. 반대로 국내 매체는 "Apple"을 "애플"로 쓴다. 같은 티커에 두 표기를 걸어야
양쪽 기사가 같은 종목으로 모인다(중복 매칭은 extract_impact_tags가 티커 기준으로 제거한다).

### 주의 — 등재하면 안 되는 이름
- 흔한 영어 단어와 겹치는 사명: Broadcom의 "avgo"는 안전하지만 Visa("visa")·
  Block("block")·Shell("shell")은 일반 명사와 충돌한다.
- 2글자 이하 티커·약칭(예: "hd", "gs"): 단어 경계를 넣어도 오탐이 남는다.
- 한글 2글자 보통명사와 겹치는 사명(예: "한화"는 안전하나 "대한"·"현대"는 단독 등재 금지 —
  "현대차"·"현대건설"처럼 구체적으로 적는다).
"""
from __future__ import annotations

ENTITIES: dict[str, tuple[str, str, str]] = {
    # ── 국내 대형주 ──
    "삼성전자": ("005930", "삼성전자", "KRX"),
    "samsung electronics": ("005930", "삼성전자", "KRX"),
    "sk하이닉스": ("000660", "SK하이닉스", "KRX"),
    "하이닉스": ("000660", "SK하이닉스", "KRX"),
    "sk hynix": ("000660", "SK하이닉스", "KRX"),
    "네이버": ("035420", "NAVER", "KRX"),
    "naver": ("035420", "NAVER", "KRX"),
    "카카오": ("035720", "카카오", "KRX"),
    "kakao": ("035720", "카카오", "KRX"),
    "현대차": ("005380", "현대차", "KRX"),
    "hyundai motor": ("005380", "현대차", "KRX"),
    "기아": ("000270", "기아", "KRX"),
    "lg에너지솔루션": ("373220", "LG에너지솔루션", "KRX"),
    "lg energy solution": ("373220", "LG에너지솔루션", "KRX"),
    "lg전자": ("066570", "LG전자", "KRX"),
    "lg electronics": ("066570", "LG전자", "KRX"),
    "포스코홀딩스": ("005490", "POSCO홀딩스", "KRX"),
    "posco": ("005490", "POSCO홀딩스", "KRX"),
    "삼성바이오로직스": ("207940", "삼성바이오로직스", "KRX"),
    "셀트리온": ("068270", "셀트리온", "KRX"),
    "celltrion": ("068270", "셀트리온", "KRX"),
    "kb금융": ("105560", "KB금융", "KRX"),
    "신한지주": ("055550", "신한지주", "KRX"),
    "한화에어로스페이스": ("012450", "한화에어로스페이스", "KRX"),
    "한화오션": ("042660", "한화오션", "KRX"),
    "hd현대중공업": ("329180", "HD현대중공업", "KRX"),
    "두산에너빌리티": ("034020", "두산에너빌리티", "KRX"),
    "에코프로비엠": ("247540", "에코프로비엠", "KRX"),
    "삼성sdi": ("006400", "삼성SDI", "KRX"),
    "sk이노베이션": ("096770", "SK이노베이션", "KRX"),
    "현대모비스": ("012330", "현대모비스", "KRX"),

    # ── 미국 대형주 ──
    "nvidia": ("NVDA", "NVIDIA", "NASDAQ"),
    "엔비디아": ("NVDA", "NVIDIA", "NASDAQ"),
    "apple": ("AAPL", "Apple", "NASDAQ"),
    "애플": ("AAPL", "Apple", "NASDAQ"),
    "microsoft": ("MSFT", "Microsoft", "NASDAQ"),
    "마이크로소프트": ("MSFT", "Microsoft", "NASDAQ"),
    "tesla": ("TSLA", "Tesla", "NASDAQ"),
    "테슬라": ("TSLA", "Tesla", "NASDAQ"),
    "amd": ("AMD", "AMD", "NASDAQ"),
    "tsmc": ("TSM", "TSMC", "NYSE"),
    "amazon": ("AMZN", "Amazon", "NASDAQ"),
    "아마존": ("AMZN", "Amazon", "NASDAQ"),
    "google": ("GOOGL", "Alphabet", "NASDAQ"),
    "alphabet": ("GOOGL", "Alphabet", "NASDAQ"),
    "구글": ("GOOGL", "Alphabet", "NASDAQ"),
    "meta": ("META", "Meta", "NASDAQ"),
    "메타": ("META", "Meta", "NASDAQ"),
    "micron": ("MU", "Micron", "NASDAQ"),
    "마이크론": ("MU", "Micron", "NASDAQ"),
    "intel": ("INTC", "Intel", "NASDAQ"),
    "인텔": ("INTC", "Intel", "NASDAQ"),
    "broadcom": ("AVGO", "Broadcom", "NASDAQ"),
    "브로드컴": ("AVGO", "Broadcom", "NASDAQ"),
    "netflix": ("NFLX", "Netflix", "NASDAQ"),
    "넷플릭스": ("NFLX", "Netflix", "NASDAQ"),
    "berkshire hathaway": ("BRK-B", "Berkshire Hathaway", "NYSE"),
    "버크셔": ("BRK-B", "Berkshire Hathaway", "NYSE"),
    "sandisk": ("SNDK", "SanDisk", "NASDAQ"),
    "샌디스크": ("SNDK", "SanDisk", "NASDAQ"),
    "cisco": ("CSCO", "Cisco", "NASDAQ"),
    "시스코": ("CSCO", "Cisco", "NASDAQ"),
    "qualcomm": ("QCOM", "Qualcomm", "NASDAQ"),
    "퀄컴": ("QCOM", "Qualcomm", "NASDAQ"),
    "palantir": ("PLTR", "Palantir", "NASDAQ"),
    "팔란티어": ("PLTR", "Palantir", "NASDAQ"),
    "eli lilly": ("LLY", "Eli Lilly", "NYSE"),
    "일라이 릴리": ("LLY", "Eli Lilly", "NYSE"),
    "jpmorgan": ("JPM", "JPMorgan", "NYSE"),
    "제이피모건": ("JPM", "JPMorgan", "NYSE"),
    "exxon": ("XOM", "Exxon Mobil", "NYSE"),
    "엑슨모빌": ("XOM", "Exxon Mobil", "NYSE"),
    "boeing": ("BA", "Boeing", "NYSE"),
    "보잉": ("BA", "Boeing", "NYSE"),
    "coinbase": ("COIN", "Coinbase", "NASDAQ"),
    "코인베이스": ("COIN", "Coinbase", "NASDAQ"),
    "asml": ("ASML", "ASML", "NASDAQ"),
}
