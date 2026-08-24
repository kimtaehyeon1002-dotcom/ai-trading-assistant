"""News v2 생성 → docs/news/index.html(4탭 배타 매핑) + docs/news/YYYY-MM-DD/ 날짜 아카이브.

design/03. v1 생성기(generators/news/generate.py)·템플릿(templates/news.html)은 롤백 대상으로
보존한다(design/20 Phase 5 리스크·롤백 — "생성기 파일 교체 단위", Phase 4 Dashboard와 동일 패턴).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from datetime import timedelta

from calculators import news_keywords, news_levels
from calculators.news_categories import TAB_LABELS, primary_category
from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from models.news import NewsArticle
from utils.dates import fmt_kst, now_kst, to_kst

TABS: tuple[str, ...] = ("us_market", "kr_market", "macro", "breaking")
_PER_TAB_LIMIT = 30
_RADAR_WINDOW_H = 24  # design/03 §3-5 "최근 24시간"
_RADAR_TOP_N = 6


def _tabbed(articles: list[NewsArticle]) -> dict[str, list[NewsArticle]]:
    """4탭 배타 배정 — 게재 기준(4탭 중 하나에 매칭) 미달 기사는 어느 리스트에도 나타나지 않는다."""
    by_tab: dict[str, list[NewsArticle]] = {t: [] for t in TABS}
    for a in articles:
        cat = primary_category(a)
        if cat in by_tab:
            by_tab[cat].append(a)
    return by_tab


def _counters(published_ids: set[str]) -> dict:
    # design/25 Phase B: 수집 호출은 파이프라인 몫이다(생성기는 외부 소스를 직접 부르지 않는다).
    return pipelines.get_news_counters(published_ids)


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


def _radar(published: list[NewsArticle], window_h: int | None = _RADAR_WINDOW_H) -> list[dict]:
    """키워드 레이더 — **게재된** 기사만 집계한다(design/03 §3-5 "게재 기사에서 추출").

    수집 전체가 아니라 화면에 실린 것만 세야 카드와 리스트가 같은 사실을 말한다.
    window_h=None이면 창 제한 없이 전량(날짜 아카이브는 그날 하루가 곧 창이다).
    """
    subset = published
    if window_h is not None:
        cutoff = now_kst() - timedelta(hours=window_h)
        subset = [a for a in published if a.published and to_kst(a.published) >= cutoff]
    return news_keywords.rank(subset, _RADAR_TOP_N)


def _render_page(ctx: dict, out: Path) -> Path:
    return render("pages/news_v2.html", ctx, out)


def generate() -> Path:
    articles = pipelines.get_news()
    # 관련종목 태깅(news_entities)은 파이프라인이 저장 전에 이미 부여했다 — 여기서 다시 부르면
    # 같은 계산을 두 번 할 뿐이고, 저장 시점과 표시 시점이 갈리는 원인이 된다.
    news_levels.assign_levels(articles)
    news_keywords.assign(articles)  # 행의 data-kw와 레이더 집계가 같은 값을 쓰도록 먼저 부여

    by_tab = _tabbed(articles)
    for key in TABS:
        by_tab[key] = by_tab[key][:_PER_TAB_LIMIT]

    published = [a for group in by_tab.values() for a in group]
    published_ids = {a.id for a in published}
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
        "radar": _radar(published),
        "radar_window_label": f"최근 {_RADAR_WINDOW_H}시간",
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
            # 아카이브는 그 하루가 곧 집계 창이다(24시간 창을 겹쳐 걸면 과거 날짜는 전부 0이 된다)
            "radar": _radar([a for g in day_by_tab.values() for a in g], window_h=None),
            "radar_window_label": date,
            "archive_date": date,
        }
        _render_page(archive_ctx, DOCS_DIR / "news" / date / "index.html")

    return out
