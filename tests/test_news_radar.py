"""키워드 레이더 — 집계 규칙과 카드 렌더(design/03 §3-5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calculators import news_keywords
from calculators.news_categories import TAB_LABELS
from config import nav
from config.keywords import RADAR_KEYWORDS
from generators.base import render
from models.news import NewsArticle

TABS = ("us_market", "kr_market", "macro", "breaking")


def _a(title: str, summary: str = "", **kw) -> NewsArticle:
    return NewsArticle(title=title, link=kw.pop("link", f"http://x/{abs(hash(title))}"),
                       summary=summary, published=datetime.now(timezone.utc), **kw)


# ---------- 집계 단위: 기사 수(등장 횟수 아님) ----------

def test_counts_articles_not_occurrences():
    """한 기사가 같은 화두를 여러 번 말해도 1건 — 긴 기사 하나가 순위를 흔들면 안 된다."""
    a = _a("반도체 반도체 반도체", "반도체 반도체")
    assert news_keywords.rank([a])[0] == {"label": "반도체", "count": 1, "pct": 100}


def test_aliases_collapse_into_one_row():
    """영문 기사와 한글 기사가 같은 화두를 다루면 한 행으로 모여야 순위가 의미를 갖는다."""
    out = news_keywords.rank([_a("Fed holds rates"), _a("연준 동결"), _a("파월 발언")])
    assert out[0]["label"] == "연준" and out[0]["count"] == 3


def test_translation_text_is_counted():
    """화면에는 번역본이 보이므로 집계도 번역본을 봐야 사용자가 읽은 것과 일치한다."""
    a = _a("Chipmaker raises guidance", title_ko="반도체 업체, 가이던스 상향")
    assert "반도체" in news_keywords.labels_of(a)


def test_no_double_count_when_original_and_translation_both_hit():
    a = _a("semiconductor demand", title_ko="반도체 수요")
    assert news_keywords.labels_of(a).count("반도체") == 1


# ---------- 순위·막대 ----------

def test_ranking_is_descending_and_limited():
    arts = [_a("반도체 소식") for _ in range(5)] + [_a("실적 발표") for _ in range(3)] + [_a("배당 확대")]
    out = news_keywords.rank(arts, top_n=2)
    assert [k["label"] for k in out] == ["반도체", "실적"]
    assert [k["count"] for k in out] == [5, 3]


def test_bar_pct_is_relative_to_top():
    arts = [_a("반도체") for _ in range(4)] + [_a("배당") for _ in range(2)]
    out = news_keywords.rank(arts)
    assert out[0]["pct"] == 100 and out[1]["pct"] == 50


def test_ties_break_deterministically():
    """동점 순서가 빌드마다 흔들리면 카드가 이유 없이 달라 보인다."""
    arts = [_a("반도체 관련"), _a("배당 확대")]
    first = [k["label"] for k in news_keywords.rank(arts)]
    for _ in range(5):
        assert [k["label"] for k in news_keywords.rank(list(reversed(arts)))] == first


def test_empty_when_nothing_matches():
    """근거 없는 키워드를 지어내지 않는다(팩트 우선)."""
    assert news_keywords.rank([_a("오늘 날씨는 맑음")]) == []
    assert news_keywords.rank([]) == []


def test_assign_sets_labels_for_row_filter():
    arts = [_a("반도체 실적 호조")]
    news_keywords.assign(arts)
    assert set(arts[0].radar_labels) >= {"반도체", "실적"}


def test_radar_labels_are_not_persisted():
    """사전이 바뀌면 의미가 달라지는 파생값이라 저장소에 굳히지 않는다."""
    a = _a("반도체")
    news_keywords.assign([a])
    assert a.radar_labels
    assert "radar_labels" not in a.to_dict()
    assert NewsArticle.from_dict(a.to_dict()).radar_labels == []


# ---------- 집계 창(생성기) ----------

def test_radar_window_excludes_old_articles():
    from generators.news_v2.generate import _radar

    old = _a("반도체 옛날 기사")
    old.published = datetime.now(timezone.utc) - timedelta(hours=48)
    fresh = _a("실적 최신 기사")
    news_keywords.assign([old, fresh])
    labels = [k["label"] for k in _radar([old, fresh])]
    assert labels == ["실적"]


def test_archive_radar_uses_whole_day_not_24h_window():
    """아카이브에 24시간 창을 겹쳐 걸면 과거 날짜는 전부 0건이 된다."""
    from generators.news_v2.generate import _radar

    old = _a("반도체 옛날 기사")
    old.published = datetime.now(timezone.utc) - timedelta(days=10)
    news_keywords.assign([old])
    assert [k["label"] for k in _radar([old], window_h=None)] == ["반도체"]


# ---------- 렌더 ----------

def _ctx(radar, rows=None):
    by_tab = {t: [] for t in TABS}
    by_tab["us_market"] = rows or []
    return {
        "root": ".", "nav": nav.context(active="news"),
        "generated_at": "2026-07-31 09:00 KST", "tabs": TABS, "tab_labels": TAB_LABELS,
        "default_tab": "us_market", "counts": {k: len(v) for k, v in by_tab.items()},
        "by_tab": by_tab, "collected_total": 100, "published_total": len(rows or []),
        "briefing": [], "level_counts": {"L1": 0, "L2": 0, "L3": 0},
        "radar": radar, "radar_window_label": "최근 24시간",
        "today": "2026-07-31", "archive_date": None,
    }


def test_card_renders_labels_counts_and_bars(tmp_path):
    radar = [{"label": "반도체", "count": 29, "pct": 100}, {"label": "AI", "count": 21, "pct": 72}]
    html = render("pages/news_v2.html", _ctx(radar), tmp_path / "i.html").read_text(encoding="utf-8")
    assert 'id="news-radar"' in html
    assert "많이 언급된 키워드" in html
    assert "반도체" in html and ">29<" in html
    assert "width: 72%" in html


def test_rows_carry_keyword_attribute_for_filtering(tmp_path):
    a = _a("반도체 실적 호조")
    news_keywords.assign([a])
    html = render("pages/news_v2.html", _ctx([], [a]), tmp_path / "i.html").read_text(encoding="utf-8")
    assert 'data-kw="' in html
    assert "반도체" in html


def test_card_shows_empty_state_without_fabricating(tmp_path):
    html = render("pages/news_v2.html", _ctx([]), tmp_path / "i.html").read_text(encoding="utf-8")
    assert "집계할 키워드가 아직 없습니다" in html


def test_filter_script_is_loaded(tmp_path):
    html = render("pages/news_v2.html", _ctx([]), tmp_path / "i.html").read_text(encoding="utf-8")
    assert "static/js/news-radar.js" in html


# ---------- 사전 위생 ----------

def test_radar_vocabulary_labels_are_unique_and_nonempty():
    assert len(RADAR_KEYWORDS) == len(set(RADAR_KEYWORDS))
    for label, aliases in RADAR_KEYWORDS.items():
        assert label and aliases, f"{label}: 별칭이 비어 있다"


def test_every_label_matches_its_own_aliases():
    """별칭이 매칭 규칙(영문 단어경계)에 걸려 자기 자신도 못 잡는 사고를 막는다."""
    from calculators import keyword_match

    for label, aliases in RADAR_KEYWORDS.items():
        for alias in aliases:
            assert keyword_match.matches(alias, keyword_match.text_of(f"오늘 {alias} 관련 뉴스")), \
                f"{label}의 별칭 '{alias}'가 스스로에게 매칭되지 않는다"
