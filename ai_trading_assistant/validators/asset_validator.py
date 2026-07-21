"""자산 원장 검증 — 콤마 포함 문자열 숫자 파싱·결측 처리. 불합격은 None(생략)."""
from __future__ import annotations


def parse_amount(raw) -> float | None:
    """"1,234,567" 같은 KOA/REST 원시 문자열(또는 숫자) → float. 실패 시 None."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return None
