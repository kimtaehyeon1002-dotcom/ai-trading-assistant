"""design/20 Phase 5 정리점 → Phase 9에서 영구화 — 모닝리포트 신규 발행 영구 중단,
데이터 파이프라인은 유지.

_build_data()는 pipelines.get_market()/get_news()를 통해 실네트워크(Yahoo/RSS)를 탈 수 있으므로,
다른 테스트들과 동일하게 합성 데이터로 대체해 빠르고 결정적으로 유지한다.
"""
from __future__ import annotations

from config.settings import DOCS_DIR
from generators import pipelines
from generators.morning import generate as morning_gen
from models.market import Quote


def test_generate_always_returns_none_but_runs_pipeline(monkeypatch):
    monkeypatch.setattr(pipelines, "get_market", lambda: {"wti": Quote(symbol="wti", name="WTI", price=80.0, change_pct=1.0)})
    monkeypatch.setattr(pipelines, "get_news", lambda: [])
    result = morning_gen.generate()
    assert result is None


def test_dated_archive_is_gone():
    """design/25: **날짜별 아카이브**가 부활하지 않는다.

    2026-08-15 경로 재편으로 docs/morning/index.html이 생겼다 — 첫 화면을 이동 전용 런처로
    바꾸면서 Morning Report 본문을 이 경로로 옮긴 것이다. 은퇴 계약이 막으려던 것은
    "docs/morning/YYYY-MM-DD/" 형태의 **동결 아카이브**(v1 셸 상속으로 스타일이 깨지고 죽은
    링크를 가리키던 페이지들)이지 morning 경로 자체가 아니었으므로, 검사 대상을 그 실체로
    좁힌다. 단일 페이지는 허용하고 날짜 디렉터리는 계속 금지한다.
    """
    assert not hasattr(morning_gen, "list_dates")
    morning_dir = DOCS_DIR / "morning"
    if not morning_dir.exists():
        return
    dated = [d.name for d in morning_dir.iterdir() if d.is_dir() and d.name[:4].isdigit()]
    assert dated == [], f"날짜별 아카이브가 되살아났다: {dated}"
