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
    # ── Envelope 계약 필드(design/20 Phase 0, design/21 §1-3) — 전부 기본값 있어 기존 생성 호출 하위호환 ──
    as_of_iso: str | None = None  # 기준시각 UTC ISO8601 — 클라이언트 신선도 판정 입력
    change_abs: float | None = None  # 절대 등락폭(가능한 소스만)
    session_key: str = "none"  # kr_regular|kr_night|us_regular|globex|fx|crypto_24h|none
    ref_price: float | None = None  # 기준가(야간선물·마감 스냅샷 등락률 산출 근거)
    quality: str = "unverified"  # verified|degraded|unverified — 2소스 교차검증 결과(design/23 D)

    @property
    def up(self) -> bool | None:
        if self.change_pct is None:
            return None
        return self.change_pct >= 0
