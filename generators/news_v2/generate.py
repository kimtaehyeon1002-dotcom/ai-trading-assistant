"""News v2 생성 → docs/news/index.html(4탭 배타 매핑) + docs/news/YYYY-MM-DD/ 날짜 아카이브.

design/03. v1 생성기(generators/news/generate.py)·템플릿(templates/news.html)은 롤백 대상으로
보존한다(design/20 Phase 5 리스크·롤백 — "생성기 파일 교체 단위", Phase 4 Dashboard와 동일 패턴).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from calculators import news_entities, news_levels
from calculators.news_categories import TAB_LABELS, primary_category
from collectors import news_collector
from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from models.news import NewsArticle
from repositories import news_counters
from utils.dates import fmt_kst, now_kst, to_kst

TABS: tuple[str, ...] = ("us_market", "kr_market", "macro", "breaking")
_PER_TAB_LIMIT = 30


def _tabbed(articles: list[NewsArticle]) -> dict[str, list[NewsArticle]]:
    """4탭 배타 배정 — 게재 기준(4탭 중 하나에 매칭) 미달 기사는 어느 리스트에도 나타나지 않는다."""
    by_tab: dict[str, list[NewsArticle]] = {t: [] for t in TABS}
    for a in articles:
        cat = primary_category(a)
        if cat in by_tab:
            by_tab[cat].append(a)
    return by_tab


def _counters(published_ids: set[str]) -> dict:
    raw = news_collector.collect()  # 이미 pipelines.get_news()가 호출해 메모이즈됨 — 추가 수집 없음
    collected_ids = {r.get("link", "") for r in raw if r.get("link")}
    return news_counters.update(collected_ids, published_ids)


def _briefing(articles: list[NewsArticle], n: int = 3) -> list[NewsArticle]:
    """모닝 브리핑 — L3 우선, 부족하면 L2로 보충(design/03 §3-3, violet 미사용 일반 캡션)."""
    by_level = {"L3": [], "L2": [], "L1": []}
    for a in articles:
        by_level.setdefault(a.level, by_level["L1"]).append(a)
    picked: list[NewsArticle] = []
    for level in ("L3", "L2"):
        for a in by_level[level]:
            if len(picked) >= n:
                break
            picked.append(a)
    return picked[:n]


def _level_counts(articles: list[NewsArticle]) -> dict[str, int]:
    counts = {"L1": 0, "L2": 0, "L3": 0}
    for a in articles:
        counts[a.level] = counts.get(a.level, 0) + 1
    return counts


def _archive_groups(articles: list[NewsArticle]) -> dict[str, list[NewsArticle]]:
    groups: dict[str, list[NewsArticle]] = defaultdict(list)
    for a in articles:
        if a.published:
            groups[to_kst(a.published).strftime("%Y-%m-%d")].append(a)
    return groups


def _render_page(ctx: dict, out: Path) -> Path:
    return render("pages/news_v2.html", ctx, out)


def generate() -> Path:
    articles = pipelines.get_news()
    news_entities.assign(articles)
    news_levels.assign_levels(articles)

    by_tab = _tabbed(articles)
    for key in TABS:
        by_tab[key] = by_tab[key][:_PER_TAB_LIMIT]

    published_ids = {a.id for group in by_tab.values() for a in group}
    counters = _counters(published_ids)

    today = now_kst().strftime("%Y-%m-%d")
    today_articles = [a for a in articles if a.published and to_kst(a.published).strftime("%Y-%m-%d") == today]

    base_ctx = {
        "root": "..",
        "nav": nav.context(active="news"),
        "generated_at": fmt_kst(now_kst()) + " KST",
        "tabs": TABS,
        "tab_labels": TAB_LABELS,
        "default_tab": "us_market",
        "counts": {k: len(v) for k, v in by_tab.items()},
        "by_tab": by_tab,
        "collected_total": counters["collected_total"],
        "published_total": counters["published_total"],
        "briefing": _briefing(today_articles or articles),
        "level_counts": _level_counts(today_articles),
        "today": today,
        "archive_date": None,
    }
    out = _render_page(base_ctx, DOCS_DIR / "news" / "index.html")

    for date, day_articles in _archive_groups(articles).items():
        day_by_tab = _tabbed(day_articles)
        archive_ctx = {
            **base_ctx,
            "root": "../..",
            "nav": nav.context(active="news"),
            "counts": {k: len(v) for k, v in day_by_tab.items()},
            "by_tab": day_by_tab,
            "briefing": _briefing(day_articles),
            "level_counts": _level_counts(day_articles),
            "archive_date": date,
        }
        _render_page(archive_ctx, DOCS_DIR / "news" / date / "index.html")

    return out
