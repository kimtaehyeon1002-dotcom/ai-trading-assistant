"""Phase 3 — Theme Scoring Engine(순수 계산) + 모닝리포트 스텁 가드레일. 오프라인 실행 가능.

engine/pipeline은 sqlalchemy 의존 → Docker/uv 환경. signals/scoring/prompts는 stdlib만.
"""
from __future__ import annotations

from app.agents.prompts import morning_report as M
from app.analytics.theme_scoring.scoring import (
    STYLE_WEIGHTS,
    composite_scores,
    robust_zscore,
    winsorize,
    zscore,
)
from app.analytics.theme_scoring.signals import Constituent, theme_raw_signals
from app.compliance.guard import guard_output

_BENCH = {"1d": 0.0, "5d": 0.0, "20d": 0.0}


def _raws():
    strong = [
        Constituent(1, mcap=2.0, ret={"1d": 3.0, "5d": 5.0}, vol=200, avg_vol=100, news_recent=10, news_baseline=2),
        Constituent(2, mcap=1.0, ret={"1d": 2.0, "5d": 4.0}, vol=150, avg_vol=100, news_recent=6, news_baseline=3),
    ]
    weak = [
        Constituent(3, mcap=1.0, ret={"1d": -2.0, "5d": -3.0}, vol=80, avg_vol=100, news_recent=1, news_baseline=4),
    ]
    mid = [Constituent(4, mcap=1.0, ret={"1d": 0.5, "5d": 0.0}, vol=100, avg_vol=100, news_recent=3, news_baseline=3)]
    return {
        "ai_semi": theme_raw_signals(strong, benchmark_ret=_BENCH),
        "laggard": theme_raw_signals(weak, benchmark_ret=_BENCH),
        "neutral": theme_raw_signals(mid, benchmark_ret=_BENCH),
    }


def test_ranking_separates_and_is_monotonic():
    res = composite_scores(_raws(), style="swing")
    keys = [r.key for r in res]
    assert keys == ["ai_semi", "neutral", "laggard"]
    assert len({r.rank for r in res}) == 3  # 랭크 유니크(타이 없음)
    assert res[0].score > res[1].score > res[2].score


def test_robust_zscore_preserves_order():
    rz = robust_zscore([3.867, 0.2, -1.8])
    assert rz[0] > rz[1] > rz[2]


def test_winsorize_small_n_no_clamp_large_n_clamps():
    assert winsorize([3.867, 0.2, -1.8]) == [3.867, 0.2, -1.8]  # n=3, kcut=0
    assert winsorize([0, 0, 0, 0, 100], 0.2)[-1] == 0  # n=5, p=.2 → kcut=1


def test_zscore_zero_variance():
    assert zscore([5, 5, 5]) == [0.0, 0.0, 0.0]


def test_style_weights_sum_to_one():
    for w in STYLE_WEIGHTS.values():
        assert abs(sum(w.values()) - 1.0) < 1e-9


def test_empty_theme_neutral_missing():
    raw = theme_raw_signals([], benchmark_ret=_BENCH)
    assert raw.missing == ["price", "volume", "attention", "news"]


def test_single_theme_percentile_mid():
    res = composite_scores({"only": theme_raw_signals([Constituent(1, ret={"1d": 1.0})], benchmark_ret=_BENCH)})
    assert len(res) == 1 and res[0].percentile == 50.0 and res[0].rank == 1


def test_morning_stub_passes_guardrail():
    ctx = {
        "report_date": "2026-06-24",
        "fx": {"rate": 1380.0, "source": "yfinance_fx", "as_of": "2026-06-24T00:00:00+00:00"},
        "themes_us": [{"theme": "미국 빅테크", "score": 75.0, "rank": 1}],
        "themes_kr": [{"theme": "한국 반도체", "score": 60.0, "rank": 1}],
        "news": [{"title": "시장 동향 요약", "source": "rss", "published_at": "2026-06-23"}],
    }
    md = M.stub_morning_markdown(ctx)
    res = guard_output(md)
    assert res.blocked is False, res.categories  # 매수/매도·목표가 트리거 없어야 함
    for h in (M.H_MARKET, M.H_US, M.H_KR, M.H_NEWS, M.H_IMPACT):
        assert h in md
