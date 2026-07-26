"""generators/pipelines.py — get_market()/get_news()는 clear_cache() 전까지 재수집하지 않는다.

build.run_build()이 여러 생성기에서 동일 데이터를 공유하려고 도입한 프로세스 내 메모이즈다
(데스크톱 앱처럼 한 프로세스에서 run_build()를 여러 번 호출할 때는 매번 clear_cache()로
무효화되므로 새 빌드는 항상 새로 수집한다 — build.py에서 검증).
"""
from __future__ import annotations

from generators import pipelines


def test_get_market_memoizes_until_clear_cache(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_collect():
        calls["n"] += 1
        return {}

    monkeypatch.setattr(pipelines.kiwoom_collector, "collect", lambda: {})
    monkeypatch.setattr(pipelines.market_collector, "collect", fake_collect)
    monkeypatch.setattr(pipelines.market_repository, "CACHE_DIR", tmp_path)

    pipelines.clear_cache()
    pipelines.get_market()
    pipelines.get_market()
    assert calls["n"] == 1, "같은 run 안에서는 재수집하면 안 된다"

    pipelines.clear_cache()
    pipelines.get_market()
    assert calls["n"] == 2, "clear_cache() 이후에는 다시 수집해야 한다"


def test_get_news_memoizes_until_clear_cache(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_collect():
        calls["n"] += 1
        return []

    monkeypatch.setattr(pipelines.news_collector, "collect", fake_collect)
    monkeypatch.setattr(pipelines.news_repository, "_STORE", tmp_path / "news_articles.json")

    pipelines.clear_cache()
    pipelines.get_news()
    pipelines.get_news()
    assert calls["n"] == 1

    pipelines.clear_cache()
    pipelines.get_news()
    assert calls["n"] == 2
