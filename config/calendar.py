"""세션·휴장 달력 — 세션 라벨/카운트다운/CLOSED-SNAPSHOT 세션우선 판정의 공통 입력.

design/21 §6-3 규격. 저빈도(연 1회) 수기 관리 데이터이며 자동 수집 소스가 없다.
holidays는 비워두면 월~금 정규장 요일만으로 판정된다(공휴일 미반영) — 매년 초 수기 갱신 필요.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MarketSession:
    market: str  # "kr" | "us"
    regular_open: str  # 거래소 현지시각 "HH:MM"(kr=KST, us=ET)
    regular_close: str
    pre_open: str | None = None  # 장전 구간 시작(카운트다운용)
    post_close: str | None = None  # 장후 구간 종료
    holidays: tuple[str, ...] = field(default_factory=tuple)  # "YYYY-MM-DD", 연 1회 수기 등재


# 실측 정규장 시각: KRX 09:00–15:30 KST, NYSE/NASDAQ 09:30–16:00 ET.
SESSIONS: dict[str, MarketSession] = {
    "kr": MarketSession(market="kr", regular_open="09:00", regular_close="15:30", pre_open="08:30"),
    "us": MarketSession(market="us", regular_open="09:30", regular_close="16:00", pre_open="09:00"),
}

# KRX 야간파생시장(2025-06 개설) — 18:00 개시 ~ **익일** 05:00 마감(자정을 넘는 유일한 세션이라
# MarketSession(open<close 전제)에 넣지 않고 별도 상수로 둔다). 야간선물 수집은 이 창 안에서만
# 유효한 시세를 얻는다: 05:00 마감 뒤에 조회하면 현재가=기준가인 flat 스냅샷이 나오며,
# 그것을 저장하면 밤사이 실제 등락이 통째로 유실된다(design/23 P2의 근본 원인).
KR_NIGHT_OPEN = "18:00"
KR_NIGHT_CLOSE = "05:00"


def is_kr_night_session(dt: datetime) -> bool:
    """dt(KST)가 야간파생 세션 창(18:00~익일 05:00) 안인가.

    자정을 넘는 구간이므로 '개시 이후' 또는 '마감 이전' 어느 한쪽만 만족해도 세션 중이다.
    휴장일(주말·공휴일)은 여기서 판정하지 않는다 — 세션 창 판정과 영업일 판정은 책임이 다르고,
    실제 수집은 '시세가 flat이면 버린다'는 별도 방어가 이미 있다.
    """
    hhmm = dt.strftime("%H:%M")
    return hhmm >= KR_NIGHT_OPEN or hhmm < KR_NIGHT_CLOSE
