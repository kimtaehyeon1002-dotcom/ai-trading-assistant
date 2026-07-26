"""calculators/news_rank.py — 가중치 후 최신순 TOP N, 결측 published 처리."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calculators.news_rank import top
from models.news import NewsArticle


def _article(title, categories=None, published=None):
    return NewsArticle(
        title=title, link=f"http://x/{title}", summary="",
        categories=categories or [], published=published,
    )


def test_missing_published_ranks_as_oldest_not_newest():
    now = datetime.now(timezone.utc)
    dated = _article("dated", published=now)
    undated = _article("undated", published=None)
    ranked = top([undated, dated], n=2)
    assert [a.title for a in ranked] == ["dated", "undated"]


def test_higher_weight_still_wins_even_when_undated():
    now = datetime.now(timezone.utc)
    breaking_undated = _article("breaking_undated", categories=["breaking"], published=None)
    plain_dated = _article("plain_dated", categories=[], published=now)
    ranked = top([plain_dated, breaking_undated], n=2)
    assert ranked[0].title == "breaking_undated"


def test_top_n_orders_by_recency_within_same_weight():
    now = datetime.now(timezone.utc)
    older = _article("older", published=now - timedelta(hours=2))
    newer = _article("newer", published=now)
    ranked = top([older, newer], n=2)
    assert [a.title for a in ranked] == ["newer", "older"]
