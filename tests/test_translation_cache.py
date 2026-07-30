"""번역 캐시 — CI 실행 간 번역 누적(design/24).

실제 사고 재현: cache/(gitignored) 저장소만 쓰던 시절, CI는 매 실행이 새 체크아웃이라
번역이 남지 않아 "최신 N건"만 매번 다시 번역했고 그보다 오래된 영어 기사는 영원히
원문으로 남았다(배포 페이지 us_market 30건 중 11건이 영어, 전부 목록 하위 기사).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models.news import NewsArticle
from repositories import translation_cache


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(translation_cache, "_CACHE", tmp_path / "news_translations.json")


def _en(title="Fed cuts rates", link="http://x/1", summary="Yields fall"):
    return NewsArticle(title=title, link=link, summary=summary, lang="en",
                       published=datetime.now(timezone.utc))


def test_translation_survives_a_fresh_checkout():
    """CI 새 체크아웃 시나리오 — 저장소는 비어도 커밋된 캐시가 번역을 되살린다."""
    done = _en()
    done.title_ko, done.summary_ko = "연준 금리 인하", "수익률 하락"
    translation_cache.save_from([done])

    fresh = _en()  # 새 실행에서 RSS로부터 다시 만들어진 객체(번역 없음)
    assert translation_cache.apply_to([fresh]) == 1
    assert fresh.title_ko == "연준 금리 인하"
    assert fresh.summary_ko == "수익률 하락"


def test_korean_articles_are_not_touched():
    ko = NewsArticle(title="코스피 상승", link="http://x/ko", lang="ko",
                     published=datetime.now(timezone.utc))
    assert translation_cache.apply_to([ko]) == 0
    assert ko.title_ko is None


def test_existing_translation_is_not_overwritten():
    cached = _en()
    cached.title_ko, cached.summary_ko = "캐시본", "캐시요약"
    translation_cache.save_from([cached])

    live = _en()
    live.title_ko, live.summary_ko = "방금 번역본", "방금 요약"
    translation_cache.apply_to([live])
    assert live.title_ko == "방금 번역본"  # 이미 붙은 번역이 우선


def test_save_merges_instead_of_overwriting():
    """CI·데스크톱 공유 원장 — 통째로 덮으면 상대가 쌓은 번역이 유실된다."""
    a = _en(link="http://x/a")
    a.title_ko, a.summary_ko = "가", ""
    translation_cache.save_from([a])

    b = _en(link="http://x/b")
    b.title_ko, b.summary_ko = "나", ""
    translation_cache.save_from([b])

    cache = translation_cache.load()
    assert len(cache) == 2, "두 번째 저장이 첫 번째 항목을 지웠다"


def test_untranslated_articles_are_not_cached():
    translation_cache.save_from([_en()])  # title_ko 없음
    assert translation_cache.load() == {}


def test_cache_is_bounded_and_keeps_newest(monkeypatch):
    monkeypatch.setattr(translation_cache, "MAX_ENTRIES", 3)
    for i in range(5):
        a = _en(link=f"http://x/{i}")
        a.title_ko, a.summary_ko = f"번역{i}", ""
        translation_cache.save_from([a])
    assert len(translation_cache.load()) <= 3


def test_older_articles_eventually_get_translated_across_runs(monkeypatch):
    """상한 때문에 이번 실행에 밀린 기사도 다음 실행에서 번역된다(캐시가 앞 40건을 흡수).

    캐시가 없던 시절에는 매 실행이 같은 최신 기사부터 다시 시작해 하위 기사에
    영영 순번이 오지 않았다 — 이 테스트가 그 회귀를 막는다.
    """
    from calculators import news_translate

    monkeypatch.setattr(news_translate, "_translate", lambda t: f"[KO]{t}")
    articles = [_en(title=f"h{i}", link=f"http://x/{i}") for i in range(5)]

    # 1회차: 상한 2건
    news_translate.translate_missing(articles, limit=2)
    translation_cache.save_from(articles)
    assert sum(1 for a in articles if a.title_ko) == 2

    # 2회차: RSS에서 새 객체로 다시 수집됨 → 캐시 적용 후 남은 것만 번역
    round2 = [_en(title=f"h{i}", link=f"http://x/{i}") for i in range(5)]
    translation_cache.apply_to(round2)
    news_translate.translate_missing(round2, limit=2)
    assert sum(1 for a in round2 if a.title_ko) == 4, "밀린 기사가 다음 실행에 번역되지 않았다"
