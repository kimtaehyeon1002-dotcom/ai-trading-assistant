"""세션·휴장 달력 — 세션 라벨/카운트다운/CLOSED-SNAPSHOT 세션우선 판정의 공통 입력.

design/21 §6-3 규격. 저빈도(연 1회) 수기 관리 데이터이며 자동 수집 소스가 없다.
holidays는 비워두면 월~금 정규장 요일만으로 판정된다(공휴일 미반영) — 매년 초 수기 갱신 필요.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class MarketSession:
    market: str  # "kr" | "us"
    regular_open: str  # 거래소 현지시각 "HH:MM"(kr=KST, us=ET)
    regular_close: str
    pre_open: str | None = None  # 장전 구간 시작(카운트다운용)
    post_close: str | None = None  # 장후 구간 종료
    holidays: tuple[str, ...] = field(default_factory=tuple)  # "YYYY-MM-DD", 연 1회 수기 등재


# 실측 정규장 시각: KRX 09:00–15:30 KST, NYSE/NASDAQ 09:30–16:00 ET.
# 날짜가 고정된 한국 법정공휴일만 등재한다. 음력 기반(설날·추석·부처님오신날)과 대체공휴일은
# 해마다 날짜가 달라 여기 넣으려면 그 해 관보를 확인해야 한다 — **확인 없이 추정해 넣지 않는다**
# (틀린 휴장일은 없는 것보다 나쁘다: 열린 장을 닫혔다고 표시한다). 미등재분은 아래 주의 참고.
_KR_FIXED_HOLIDAYS = ("01-01", "03-01", "05-05", "06-06", "08-15", "10-03", "10-09", "12-25")

SESSIONS: dict[str, MarketSession] = {
    "kr": MarketSession(market="kr", regular_open="09:00", regular_close="15:30", pre_open="08:30"),
    "us": MarketSession(market="us", regular_open="09:30", regular_close="16:00", pre_open="09:00"),
}


def holiday_label(session: MarketSession, d: date) -> str | None:
    """d가 휴장일이면 사유("주말"/"공휴일"), 영업일이면 None.

    주말 판정은 확실하지만 공휴일은 등재된 것만 안다 — 음력 명절·대체공휴일이 빠져 있으므로
    "None이면 반드시 영업일"이라고 단정할 수 없다. 호출부는 이 한계를 화면에 드러내야 한다.
    """
    if d.weekday() >= 5:
        return "주말"
    if d.strftime("%Y-%m-%d") in session.holidays or (
        session.market == "kr" and d.strftime("%m-%d") in _KR_FIXED_HOLIDAYS
    ):
        return "공휴일"
    return None


def is_trading_day(session: MarketSession, d: date) -> bool:
    """d가 정규장이 열리는 날인가(주말·등재 공휴일 제외)."""
    return holiday_label(session, d) is None


def next_trading_day(session: MarketSession, d: date, max_lookahead: int = 10) -> date | None:
    """d **다음** 영업일. 연휴가 길어도 찾도록 여유를 두되 무한 탐색은 하지 않는다."""
    for step in range(1, max_lookahead + 1):
        cand = d + timedelta(days=step)
        if is_trading_day(session, cand):
            return cand
    return None

# KRX 야간파생시장(2025-06 개설) — 18:00 개시 ~ **익일** 05:00 마감(자정을 넘는 유일한 세션이라
# MarketSession(open<close 전제)에 넣지 않고 별도 상수로 둔다). 야간선물 수집은 이 창 안에서만
# 유효한 시세를 얻는다: 05:00 마감 뒤에 조회하면 현재가=기준가인 flat 스냅샷이 나오며,
# 그것을 저장하면 밤사이 실제 등락이 통째로 유실된다(design/23 P2의 근본 원인).
KR_NIGHT_OPEN = "18:00"
KR_NIGHT_CLOSE = "05:00"

# KRX 지수선물 정규장 마감 — 현물(15:30)보다 15분 늦다. 야간 등락률의 올바른 기준가
# (=당일 정규장 종가)를 확보하는 수집 창의 시작점이므로 현물 마감으로 대신할 수 없다:
# 15:30~15:45 사이에 조회하면 아직 장중인 값을 '종가'로 굳혀 저장하게 된다.
KR_FUTURES_REGULAR_CLOSE = "15:45"


def is_kr_night_session(dt: datetime) -> bool:
    """dt(KST)가 야간파생 세션 창(18:00~익일 05:00) 안인가.

    자정을 넘는 구간이므로 '개시 이후' 또는 '마감 이전' 어느 한쪽만 만족해도 세션 중이다.
    휴장일(주말·공휴일)은 여기서 판정하지 않는다 — 세션 창 판정과 영업일 판정은 책임이 다르고,
    실제 수집은 '시세가 flat이면 버린다'는 별도 방어가 이미 있다.
    """
    hhmm = dt.strftime("%H:%M")
    return hhmm >= KR_NIGHT_OPEN or hhmm < KR_NIGHT_CLOSE


def is_kr_futures_close_window(dt: datetime) -> bool:
    """dt(KST)가 지수선물 정규장 마감(15:45) ~ 야간 개시(18:00) 창 안인가.

    이 창에서만 opt50001의 현재가가 **당일 정규장 종가**로 확정돼 있다(장중엔 아직 미확정,
    야간 개시 후엔 이미 야간 체결가로 갈아탄다). 야간 등락률의 기준가는 여기서만 얻는다.
    """
    hhmm = dt.strftime("%H:%M")
    return KR_FUTURES_REGULAR_CLOSE <= hhmm < KR_NIGHT_OPEN


def night_base_trading_day(dt: datetime) -> date:
    """야간 관측 시각 dt(KST) → 그 세션의 기준 거래일(=직전 정규장이 열린 날).

    야간장은 자정을 넘으므로 '관측한 날짜'와 '기준 거래일'이 갈린다: 07-30 22:30 관측과
    07-31 00:02 관측은 **같은 세션**이고 둘 다 기준 거래일은 07-30이다. 이 대응을 틀리면
    하루 어긋난 종가를 기준으로 잡아 등락률이 통째로 잘못 나온다.
    """
    return dt.date() if dt.strftime("%H:%M") >= KR_NIGHT_OPEN else dt.date() - timedelta(days=1)
