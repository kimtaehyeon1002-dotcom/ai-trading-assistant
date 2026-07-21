"""세션·휴장 달력 — 세션 라벨/카운트다운/CLOSED-SNAPSHOT 세션우선 판정의 공통 입력.

design/21 §6-3 규격. 저빈도(연 1회) 수기 관리 데이터이며 자동 수집 소스가 없다.
holidays는 비워두면 월~금 정규장 요일만으로 판정된다(공휴일 미반영) — 매년 초 수기 갱신 필요.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
