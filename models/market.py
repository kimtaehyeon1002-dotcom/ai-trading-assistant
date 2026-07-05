"""시세 dataclass. 모든 값에 source 부착(출처 추적성)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Quote:
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    currency: str = ""
    source: str = ""
    as_of: str = ""  # 기준시각(KST 표시 문자열) — 캐시 경유 값(야간선물)의 투명성용

    @property
    def up(self) -> bool | None:
        if self.change_pct is None:
            return None
        return self.change_pct >= 0
