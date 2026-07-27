"""뉴스 한글 번역(design/24 Phase A 확장) — 링크만 원문, 표시는 번역본 우선.

네트워크(실제 번역 API)는 타지 않는다 — calculators.news_translate._translate를 스텁으로
교체해 all-or-nothing 캐시 정책과 실행당 상한만 검증한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators import news_translate
from models.news import NewsArticle


def _article(title="Fed signals rate cut", summary="Bond yields fall", lang="en", link="http://x/1"):
    return NewsArticle(title=title, summary=summary, lang=lang, link=link,
                       published=datetime.now(timezone.utc))


def test_korean_articles_are_never_translated(monkeypatch):
    calls = []
    monkeypatch.setattr(news_translate, "_translate", lambda t: calls.append(t) or "번역됨")
    a = _article(lang="ko")
    news_translate.translate_missing([a], limit=10)
    assert calls == []
    assert a.title_ko is None and a.summary_ko is None


def test_english_article_gets_translated(monkeypatch):
    monkeypatch.setattr(news_translate, "_translate",
                        lambda t: f"[KO]{t}")
    a = _article(title="Fed cuts rates", summary="Yields fall")
    news_translate.translate_missing([a], limit=10)
    assert a.title_ko == "[KO]Fed cuts rates"
    assert a.summary_ko == "[KO]Yields fall"


def test_already_translated_articles_are_not_retranslated(monkeypatch):
    calls = []
    monkeypatch.setattr(news_translate, "_translate", lambda t: calls.append(t) or f"[KO]{t}")
    a = _article()
    a.title_ko = "이미 번역됨"
    news_translate.translate_missing([a], limit=10)
    assert calls == []  # 캐시 히트 — 재번역 안 함
    assert a.summary_ko is None  # 애초에 건드리지 않음


def test_summary_failure_reverts_title_too_all_or_nothing(monkeypatch):
    """제목만 성공하고 요약이 실패하면 '제목은 한글, 요약은 영어'로 영구 고착되면 안 된다."""
    def fake(t):
        return None if t == "Yields fall" else f"[KO]{t}"

    monkeypatch.setattr(news_translate, "_translate", fake)
    a = _article(title="Fed cuts rates", summary="Yields fall")
    news_translate.translate_missing([a], limit=10)
    assert a.title_ko is None and a.summary_ko is None  # 다음 실행에 통째로 재시도


def test_title_failure_leaves_article_untouched(monkeypatch):
    monkeypatch.setattr(news_translate, "_translate", lambda t: None)
    a = _article()
    news_translate.translate_missing([a], limit=10)
    assert a.title_ko is None and a.summary_ko is None


def test_empty_summary_becomes_empty_string_not_none(monkeypatch):
    """summary_ko를 None으로 두면 '아직 미번역'과 구분이 안 된다 — 빈 원문은 빈 번역으로 확정."""
    monkeypatch.setattr(news_translate, "_translate", lambda t: f"[KO]{t}")
    a = _article(summary="")
    news_translate.translate_missing([a], limit=10)
    assert a.title_ko == "[KO]Fed signals rate cut"
    assert a.summary_ko == ""


def test_per_run_limit_bounds_translation_calls(monkeypatch):
    """실행당 상한 — 무료 번역 엔드포인트 과호출로 빌드가 느려지거나 차단되는 것을 막는다."""
    calls = []
    monkeypatch.setattr(news_translate, "_translate", lambda t: calls.append(t) or f"[KO]{t}")
    articles = [_article(title=f"headline {i}", link=f"http://x/{i}") for i in range(5)]
    news_translate.translate_missing(articles, limit=2)
    translated = [a for a in articles if a.title_ko]
    assert len(translated) == 2
    # 2건만 처리 — 각 건이 제목+요약 2회 호출(호출 대상 자체를 2건으로 제한하는지 확인)
    assert calls == ["headline 0", "Bond yields fall", "headline 1", "Bond yields fall"]


def test_limit_only_counts_untranslated_candidates(monkeypatch):
    """이미 번역된 기사는 상한 소모에서 제외된다 — 캐시 히트가 다음 신규 기사의 기회를 뺏지 않는다."""
    monkeypatch.setattr(news_translate, "_translate", lambda t: f"[KO]{t}")
    cached = _article(link="http://x/cached")
    cached.title_ko, cached.summary_ko = "이미", "번역됨"
    fresh = _article(title="new headline", link="http://x/fresh")
    news_translate.translate_missing([cached, fresh], limit=1)
    assert fresh.title_ko == "[KO]new headline"
