"""Phase 5 — 포트폴리오 메트릭(순수) + 분석 스텁 가드레일. 오프라인 실행 가능.

portfolio_service는 sqlalchemy 의존 → Docker/uv 환경. metrics/prompts는 stdlib만.
"""
from __future__ import annotations

from app.agents.prompts import portfolio as P
from app.analytics.portfolio_metrics import Position, compute_portfolio_metrics
from app.compliance.guard import guard_output


def test_concentration_metrics():
    conc = [
        Position("005930.KS", 8000.0, "IT", "KR", "KRW"),
        Position("AAPL", 1000.0, "Tech", "US", "USD"),
        Position("ETH", 1000.0, "Crypto", "US", "USD"),
    ]
    m = compute_portfolio_metrics(conc, base_currency="KRW")
    assert m["n_positions"] == 3 and m["total_value"] == 10000.0
    assert abs(m["top1_weight"] - 0.8) < 1e-9
    assert m["concentration_band"] == "높음"
    assert abs(m["hhi"] - (0.64 + 0.01 + 0.01)) < 1e-9
    assert m["by_market"]["KR"]["weight"] == 0.8
    assert m["by_currency"]["USD"]["weight"] == 0.2


def test_even_portfolio_low_concentration():
    even = [Position(f"s{i}", 1000.0, "X", "KR", "KRW") for i in range(10)]
    m = compute_portfolio_metrics(even)
    assert abs(m["hhi"] - 0.1) < 1e-9 and round(m["effective_n"]) == 10
    assert m["concentration_band"] == "낮음"


def test_empty_safe():
    m = compute_portfolio_metrics([])
    assert m["n_positions"] == 0 and m["total_value"] == 0.0 and m["hhi"] == 0.0


def test_analysis_stub_passes_guardrail():
    m = compute_portfolio_metrics(
        [Position("005930.KS", 8000.0, "IT", "KR", "KRW"), Position("AAPL", 2000.0, "Tech", "US", "USD")],
        base_currency="KRW",
    )
    md = P.stub_portfolio_markdown(m)
    res = guard_output(md)
    assert res.blocked is False, res.categories  # 매수/매도·목표가·리밸런싱 지시 없음
    for h in (P.H_COMP, P.H_OBS, P.H_SCEN, P.H_RISK):
        assert h in md
    blocks = P.parse_portfolio_blocks(md)
    assert blocks["composition"] and blocks["observations"]
    assert blocks["scenarios"] and blocks["risks"]
