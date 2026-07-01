"""포트폴리오 메트릭 — 비중·집중도(HHI)·노출 코드 계산(LLM 비의존). 설계서 §1.3, §2.4.

리밸런싱 '지시'가 아니라 분산/집중을 '관찰 지표'로 산출한다. 평가액은 기준통화로 환산된 값을
입력으로 받는다(환산·시세 수집은 서비스 책임). stdlib만 의존 → 오프라인 단위 테스트 가능.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    value_base: float  # 평가액(기준통화 환산)
    sector: str | None = None
    market: str | None = None  # KR | US (국가 프록시)
    currency: str | None = None  # KRW | USD


def _band(hhi: float) -> str:
    """HHI 기준 집중도 관찰 밴드(추천 아님)."""
    if hhi >= 0.25:
        return "높음"
    if hhi >= 0.15:
        return "보통"
    return "낮음"


def _agg(positions: list[Position], keyfn, total: float) -> dict:
    d: dict[str, float] = {}
    for p in positions:
        k = keyfn(p) or "기타"
        d[k] = d.get(k, 0.0) + p.value_base
    items = sorted(d.items(), key=lambda kv: -kv[1])
    return {
        k: {"value": round(v, 2), "weight": round(v / total, 4) if total else 0.0}
        for k, v in items
    }


def compute_portfolio_metrics(positions: list[Position], *, base_currency: str = "KRW") -> dict:
    vals = [p for p in positions if p.value_base and p.value_base > 0]
    total = sum(p.value_base for p in vals)
    n = len(vals)

    weighted = sorted(
        ((p.symbol, (p.value_base / total if total else 0.0)) for p in vals),
        key=lambda x: -x[1],
    )
    w_only = [w for _, w in weighted]
    hhi = sum(w * w for w in w_only)
    eff_n = (1.0 / hhi) if hhi > 0 else 0.0

    return {
        "base_currency": base_currency,
        "total_value": round(total, 2),
        "n_positions": n,
        "hhi": round(hhi, 4),
        "effective_n": round(eff_n, 2),
        "concentration_band": _band(hhi),
        "top1_weight": round(w_only[0], 4) if w_only else 0.0,
        "top3_weight": round(sum(w_only[:3]), 4),
        "top5_weight": round(sum(w_only[:5]), 4),
        "positions": [{"symbol": s, "weight": round(w, 4)} for s, w in weighted],
        "by_sector": _agg(vals, lambda p: p.sector, total),
        "by_market": _agg(vals, lambda p: p.market, total),
        "by_currency": _agg(vals, lambda p: p.currency, total),
    }
