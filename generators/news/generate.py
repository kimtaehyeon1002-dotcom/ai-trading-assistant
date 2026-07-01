"""뉴스 센터 페이지 생성 → docs/news/index.html (카테고리별 그룹)."""
from __future__ import annotations

from pathlib import Path

from config.feeds import CATEGORY_ORDER
from config.settings import NEWS_MAX_PER_CATEGORY
from config.settings import DOCS_DIR
from core.dates import fmt_kst, now_kst
from core.logging import get_logger
from generators.base import render
from services.news import collector, store

log = get_logger("gen.news")


def generate() -> Path:
    articles = store.merge_and_save(collector.collect())
    groups: dict[str, list] = {cat: [] for cat, _ in CATEGORY_ORDER}
    for a in articles:
        for cat in a.categories:
            if cat in groups and len(groups[cat]) < NEWS_MAX_PER_CATEGORY:
                groups[cat].append(a)
    ctx = {
        "active": "news",
        "root": "..",
        "order": CATEGORY_ORDER,
        "groups": groups,
        "total": len(articles),
        "generated_at": fmt_kst(now_kst()) + " KST",
    }
    out = render("news.html", ctx, DOCS_DIR / "news" / "index.html")
    log.info("뉴스 센터 생성: %s (%d건)", out, len(articles))
    return out
