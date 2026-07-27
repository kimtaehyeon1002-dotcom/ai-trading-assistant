"""News v2 렌더 — 번역본 우선 표시 + 원문 폴백(design/24 Phase A 확장)."""
from __future__ import annotations

from datetime import datetime, timezone

from calculators.news_categories import TAB_LABELS
from config import nav
from generators.base import render
from models.news import NewsArticle

TABS = ("us_market", "kr_market", "macro", "breaking")


def _ctx(articles: list[NewsArticle]) -> dict:
    by_tab = {t: [] for t in TABS}
    by_tab["us_market"] = articles
    return {
        "root": ".",
        "nav": nav.context(active="news"),
        "generated_at": "2026-07-24 09:00 KST",
        "tabs": TABS,
        "tab_labels": TAB_LABELS,
        "default_tab": "us_market",
        "counts": {k: len(v) for k, v in by_tab.items()},
        "by_tab": by_tab,
        "collected_total": 100,
        "published_total": len(articles),
        "briefing": [],
        "level_counts": {"L1": 0, "L2": 0, "L3": 0},
        "today": "2026-07-24",
        "archive_date": None,
    }


def _article(**kw) -> NewsArticle:
    base = dict(title="Fed cuts rates", link="http://x/1", source="Reuters", lang="en",
                published=datetime.now(timezone.utc), summary="Yields fall sharply")
    base.update(kw)
    return NewsArticle(**base)


def test_translated_title_and_summary_shown_over_original(tmp_path):
    a = _article(title_ko="연준 금리 인하", summary_ko="채권 수익률 급락")
    html = render("pages/news_v2.html", _ctx([a]), tmp_path / "index.html").read_text(encoding="utf-8")
    assert "연준 금리 인하" in html
    assert "채권 수익률 급락" in html
    assert "Fed cuts rates" not in html  # 원문은 링크 href에만 남고 화면 텍스트엔 없다


def test_original_link_preserved_even_when_translated(tmp_path):
    a = _article(title_ko="연준 금리 인하", summary_ko="채권 수익률 급락", link="http://original.example/article")
    html = render("pages/news_v2.html", _ctx([a]), tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="http://original.example/article"' in html


def test_untranslated_article_falls_back_to_original_text(tmp_path):
    """번역 대기 중(title_ko=None)인 기사는 원문이 그대로 보여야 한다 — 빈 화면보다 원문이 낫다."""
    a = _article(title="Tesla beats delivery estimates")
    html = render("pages/news_v2.html", _ctx([a]), tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Tesla beats delivery estimates" in html


def test_korean_source_article_shows_original_without_translation(tmp_path):
    a = _article(title="코스피 6천대 진입", summary="외국인 매수세 지속", lang="ko",
                link="http://x/2")
    html = render("pages/news_v2.html", _ctx([a]), tmp_path / "index.html").read_text(encoding="utf-8")
    assert "코스피 6천대 진입" in html
    assert "외국인 매수세 지속" in html


def test_summary_omitted_when_identical_to_headline(tmp_path):
    """구글뉴스 등이 제목을 요약으로 반복하는 경우 — 같은 줄을 두 번 보여주지 않는다."""
    a = _article(title_ko="같은 문장", summary_ko="같은 문장")
    html = render("pages/news_v2.html", _ctx([a]), tmp_path / "index.html").read_text(encoding="utf-8")
    assert html.count("같은 문장") == 1
