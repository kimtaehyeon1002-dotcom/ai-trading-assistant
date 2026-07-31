"""키워드 레이더 — 게재 기사에서 많이 언급된 화두 집계(design/03 §3-5).

집계 단위는 **기사 수**이지 등장 횟수가 아니다. 한 기사가 "반도체"를 열 번 말해도 1건으로
센다 — 카드가 답하려는 질문이 "얼마나 많이 쓰였나"가 아니라 "몇 건이 이 화두를 다뤘나"이기
때문이다. 등장 횟수로 세면 긴 기사 하나가 순위를 통째로 흔든다.

매칭 대상에 **번역본(title_ko·summary_ko)도 포함**한다. 화면에 번역본이 보이는데 원문으로만
집계하면 사용자가 읽은 것과 카드가 세는 것이 어긋난다. 별칭 묶음(config RADAR_KEYWORDS)이
"fed↔연준"을 같은 라벨로 모으므로 이중 계상은 생기지 않는다(기사 단위 존재 여부만 본다).
"""
from __future__ import annotations

from collections import Counter

from calculators import keyword_match
from config.keywords import RADAR_KEYWORDS
from models.news import NewsArticle


def labels_of(article: NewsArticle) -> list[str]:
    """이 기사가 다루는 레이더 라벨 — 사전 등재 순서를 유지한다(표시 안정성)."""
    text = keyword_match.text_of(
        article.title, article.summary, article.title_ko or "", article.summary_ko or ""
    )
    return [label for label, aliases in RADAR_KEYWORDS.items()
            if keyword_match.any_match(aliases, text)]


def assign(articles: list[NewsArticle]) -> list[NewsArticle]:
    """기사에 radar_labels 부여(제자리) — 행 필터(data-kw)와 집계가 같은 값을 쓰도록."""
    for a in articles:
        a.radar_labels = labels_of(a)
    return articles


def rank(articles: list[NewsArticle], top_n: int = 6) -> list[dict]:
    """[{label, count, pct}] — 빈도 내림차순 Top N. 근거(count>0) 있는 라벨만.

    pct는 1위 대비 막대 길이(%)다. 전체 기사 수가 아니라 최댓값 기준이라 상위 항목이 늘
    꽉 찬 막대가 된다 — 카드의 목적이 절대 비율이 아니라 **상대 비교**이기 때문이다.
    동점은 사전 등재 순서로 갈라 빌드마다 순서가 흔들리지 않게 한다.
    """
    counts = Counter()
    for a in articles:
        labels = a.radar_labels if a.radar_labels else labels_of(a)
        counts.update(labels)
    if not counts:
        return []
    order = {label: i for i, label in enumerate(RADAR_KEYWORDS)}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], order.get(kv[0], 999)))[:top_n]
    top = ranked[0][1]
    return [{"label": label, "count": n, "pct": round(n / top * 100)} for label, n in ranked]
