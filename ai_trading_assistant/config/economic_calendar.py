"""정기 거시 이벤트 일정 — FOMC 등 사전 공지된 실제 날짜만(추정·가짜 일정 금지, design/20 Phase 6).

FOMC 회의 시각(성명 발표 14:00 ET, 의장 기자회견 14:30 ET)은 각 회의 첫째 날이 아닌 **둘째 날**
기준이다. 출처: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (2026-07-21 확인).
"""
from __future__ import annotations

# (성명 발표일 "YYYY-MM-DD", 라벨) — 각 회의 둘째 날, 시각은 14:00 ET(경제 전망 포함 회의는 *)
FOMC_2026: list[tuple[str, str]] = [
    ("2026-01-28", "FOMC 금리 결정"),
    ("2026-03-18", "FOMC 금리 결정 (경제전망 포함)"),
    ("2026-04-29", "FOMC 금리 결정"),
    ("2026-06-17", "FOMC 금리 결정 (경제전망 포함)"),
    ("2026-07-29", "FOMC 금리 결정"),
    ("2026-09-16", "FOMC 금리 결정 (경제전망 포함)"),
    ("2026-10-28", "FOMC 금리 결정"),
    ("2026-12-09", "FOMC 금리 결정 (경제전망 포함)"),
]

FOMC_STATEMENT_TIME_ET = "14:00"  # 성명 발표 시각(미 동부시간, 고정)
