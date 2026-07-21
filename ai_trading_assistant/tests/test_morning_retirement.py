"""design/20 Phase 5 정리점 → Phase 9에서 영구화 — 모닝리포트 신규 발행 영구 중단,
데이터 파이프라인은 유지.

_build_data()는 pipelines.get_market()/get_news()를 통해 실네트워크(Yahoo/RSS)를 탈 수 있으므로,
다른 테스트들과 동일하게 합성 데이터로 대체해 빠르고 결정적으로 유지한다.
"""
from __future__ import annotations

from generators import pipelines
from generators.morning import generate as morning_gen
from models.market import Quote


def test_generate_always_returns_none_but_runs_pipeline(monkeypatch):
    monkeypatch.setattr(pipelines, "get_market", lambda: {"wti": Quote(symbol="wti", name="WTI", price=80.0, change_pct=1.0)})
    monkeypatch.setattr(pipelines, "get_news", lambda: [])
    result = morning_gen.generate()
    assert result is None


def test_list_dates_still_reads_existing_archive():
    dates = morning_gen.list_dates()
    assert isinstance(dates, list)  # 아카이브가 비어있지 않다면 기존 날짜들이 그대로 조회된다
