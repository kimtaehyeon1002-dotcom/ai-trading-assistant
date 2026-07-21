"""글로벌 검색 인덱스(design/00 §7-2, design/20 Phase 7) — 3그룹 조립·스키마."""
from __future__ import annotations

from datetime import datetime, timezone

from models.news import NewsArticle
from repositories import search_repository
from tests.conftest import validator_for


def test_pages_include_all_nav_items():
    pages = search_repository._pages()
    keys = {p["key"] for p in pages}
    assert {"dashboard", "macro", "news", "stock", "financials", "ta", "asset", "portfolio", "settings"} <= keys


def test_stocks_reads_missing_universe_file_as_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(search_repository, "DOCS_DIR", tmp_path)
    assert search_repository._stocks() == []


def test_news_caps_at_max_and_preserves_fields():
    articles = [
        NewsArticle(title=f"기사{i}", link=f"https://x/{i}", source="src",
                    published=datetime.now(timezone.utc))
        for i in range(60)
    ]
    out = search_repository._news(articles)
    assert len(out) == search_repository._MAX_NEWS
    assert out[0]["title"] == "기사0"
    assert out[0]["link"] == "https://x/0"


def test_build_matches_schema(schema_registry, monkeypatch, tmp_path):
    monkeypatch.setattr(search_repository, "DOCS_DIR", tmp_path)
    articles = [NewsArticle(title="A", link="https://x", source="s", published=None)]
    body = search_repository.build(articles)
    v = validator_for("search_index.schema.json", schema_registry)
    errors = list(v.iter_errors(body))
    assert errors == [], [e.message for e in errors]
