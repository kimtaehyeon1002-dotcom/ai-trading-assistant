"""거래대금 랭킹 순수 계산 — 정렬·순위·테마 태깅(design/21 §7-1 TOP30 테이블).

수집기 원장(list[dict])을 받아 정렬된 랭킹만 만든다. Envelope/스키마 조립·모집단 캡션은
repositories/stock_repository가 담당한다(calculators는 부작용 없는 순수 함수).
"""
from __future__ import annotations

from config.themes import THEMES


def theme_of(code: str) -> str | None:
    """종목 코드가 속한 테마(config/themes.py) — Stock Hub도 재사용하므로 공개 함수로 둔다."""
    for theme, stocks in THEMES.items():
        if any(t == code for t, _name, _market in stocks):
            return theme
    return None


def top_n(rows: list[dict], n: int) -> list[dict]:
    """amount(거래대금) 내림차순 정렬 → 상위 n개에 rank·theme 부여. 원본 rows는 불변."""
    ranked = sorted(rows, key=lambda r: r.get("amount") or 0, reverse=True)[:n]
    return [{**r, "rank": i + 1, "theme": theme_of(r["code"])} for i, r in enumerate(ranked)]
