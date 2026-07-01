"""시장 요약 조립 — 규칙 기반 한 줄 헤드라인(LLM 비의존)."""
from __future__ import annotations

from models.market import MarketSummary
from services.market import fx, futures, quotes


def _headline(indices) -> str:
    named = {i.name: i for i in indices}
    parts = []
    for key in ("S&P 500", "NASDAQ", "KOSPI", "KOSDAQ"):
        q = named.get(key)
        if q and q.change_pct is not None:
            sign = "+" if q.change_pct >= 0 else ""
            parts.append(f"{key} {sign}{q.change_pct}%")
    return " · ".join(parts) if parts else "시장 데이터 수집 중"


def build_summary() -> MarketSummary:
    indices = quotes.get_indices()
    return MarketSummary(
        indices=indices,
        futures=futures.get_futures(),
        fx=fx.get_fx(),
        watchlist=quotes.get_watchlist(),
        headline=_headline(indices),
    )
