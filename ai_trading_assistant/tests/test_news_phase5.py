"""Phase 5 News(/news/) 치환 — 4탭 배타 매핑·L3 상한·first_seen_at·카운터(design/20 Phase 5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calculators.news_categories import primary_category, primary_label
from calculators.news_entities import assign as assign_impact_tags
from calculators.news_entities import extract_impact_tags
from calculators.news_levels import L3_DAILY_CAP, assign_levels
from models.news import NewsArticle
from repositories import news_repository


def _article(title="t", link="http://x/1", categories=None, published=None, summary=""):
    return NewsArticle(
        title=title, link=link, summary=summary,
        categories=categories or [], published=published or datetime.now(timezone.utc),
    )


# ---------- 4탭 배타 매핑(design/20 Phase 5 체크리스트 1, DoD 1) ----------

def test_primary_category_priority_breaking_over_everything():
    a = _article(categories=["kr_market", "macro", "breaking"])
    assert primary_category(a) == "breaking"


def test_primary_category_macro_over_market():
    a = _article(categories=["us_market", "macro"])
    assert primary_category(a) == "macro"


def test_primary_category_none_when_no_tab_category():
    """ai/semiconductor 단독은 어떤 탭에도 속하지 않는다 — 게재 기준 미달(4탭 밖)."""
    a = _article(categories=["ai", "semiconductor"])
    assert primary_category(a) is None


def test_each_article_maps_to_at_most_one_tab():
    """DoD 1 — 한 기사는 정확히 1탭(또는 0탭)에만 속한다는 것을 여러 카테고리 조합으로 확인."""
    combos = [
        ["kr_market"], ["us_market"], ["macro"], ["breaking"],
        ["kr_market", "us_market"], ["kr_market", "macro", "breaking"], ["ai"],
    ]
    for cats in combos:
        a = _article(categories=cats)
        cat = primary_category(a)
        assert cat is None or cat in ("us_market", "kr_market", "macro", "breaking")


def test_primary_label_matches_category():
    a = _article(categories=["macro"])
    assert primary_label(a) == "거시경제"


# ---------- L3 일일 상한(DoD 3) ----------

def test_l3_daily_cap_enforced_with_synthetic_overflow():
    """macro 카테고리 + 관련종목 매칭으로 점수 3점 이상인 기사를 상한보다 많이 만들어 강등을 확인.

    고정 시각을 앵커로 쓴다 — datetime.now()를 쓰면 KST 자정 부근(day 경계) 실행 시 일부 기사가
    전날 KST 날짜로 넘어가 그룹이 쪼개지며 상한 미적용처럼 보이는 flaky 실패가 났다(실측 확인:
    2026-07-22 자정 직후 실행에서 9건 전부 L3로 판정되는 회귀 재현).
    """
    anchor = datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)  # KST 정오, 자정과 충분히 먼 시각
    articles = [
        _article(
            title=f"기사 {i}", link=f"http://x/{i}",
            categories=["macro", "semiconductor"],
            summary="삼성전자 실적",  # config/entities.py 매칭 → impact_tags 발생 → 점수 4
            published=anchor - timedelta(minutes=i),
        )
        for i in range(L3_DAILY_CAP + 4)  # 상한보다 4건 더 많이
    ]
    assign_levels(articles)
    l3_count = sum(1 for a in articles if a.level == "L3")
    assert l3_count == L3_DAILY_CAP, f"L3 상한 미준수: {l3_count}건 (상한 {L3_DAILY_CAP})"
    # 초과분은 삭제가 아니라 L2로 강등되어야 한다(정보 손실 없음)
    demoted = [a for a in articles if a.level == "L2"]
    assert len(demoted) == 4


def test_l3_cap_applies_per_day_not_globally():
    """서로 다른 날짜는 각자 별도의 L3 상한을 갖는다(하루 기대 건수 개념)."""
    day1 = datetime(2026, 7, 1, 9, tzinfo=timezone.utc)
    day2 = datetime(2026, 7, 2, 9, tzinfo=timezone.utc)
    articles = [
        _article(title=f"d1-{i}", link=f"http://x/d1-{i}", categories=["macro"], summary="삼성전자", published=day1)
        for i in range(L3_DAILY_CAP + 2)
    ] + [
        _article(title=f"d2-{i}", link=f"http://x/d2-{i}", categories=["macro"], summary="삼성전자", published=day2)
        for i in range(L3_DAILY_CAP + 2)
    ]
    assign_impact_tags(articles)  # summary="삼성전자" → impact_tags 채움 → 점수 macro(2)+태그(1)=3
    assign_levels(articles)
    day1_l3 = sum(1 for a in articles if a.published == day1 and a.level == "L3")
    day2_l3 = sum(1 for a in articles if a.published == day2 and a.level == "L3")
    assert day1_l3 == L3_DAILY_CAP
    assert day2_l3 == L3_DAILY_CAP


def test_low_score_articles_stay_l1():
    a = _article(categories=[], summary="특이사항 없음")
    assign_levels([a])
    assert a.level == "L1"


# ---------- 관련 종목 태깅 ----------

def test_extract_impact_tags_matches_curated_entity():
    a = _article(title="삼성전자, HBM4 양산 공식화", summary="")
    tags = extract_impact_tags(a)
    assert any(t["ticker"] == "005930" for t in tags)


def test_extract_impact_tags_dedups_by_ticker():
    a = _article(title="SK하이닉스 실적 발표, 하이닉스 강세", summary="")
    tags = extract_impact_tags(a)
    tickers = [t["ticker"] for t in tags]
    assert tickers.count("000660") == 1  # "sk하이닉스"·"하이닉스" 별칭 중복 매칭 제거


def test_extract_impact_tags_empty_when_no_match():
    a = _article(title="오늘의 날씨", summary="맑음")
    assert extract_impact_tags(a) == []


# ---------- first_seen_at 스탬핑(신규만, 재병합 시 보존) ----------

def test_merge_preserves_first_seen_at_across_rebuilds(tmp_path, monkeypatch):
    from config import settings as config_settings
    monkeypatch.setattr(config_settings, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(news_repository, "_STORE", tmp_path / "news_articles.json")

    a1 = _article(title="기사", link="http://x/stable")
    first = news_repository.merge_and_save([a1])
    original_seen = first[0].first_seen_at
    assert original_seen is not None

    a2 = _article(title="기사(갱신)", link="http://x/stable")  # 같은 링크 = 같은 id, 재병합
    second = news_repository.merge_and_save([a2])
    assert second[0].first_seen_at == original_seen, "재병합 시 first_seen_at을 덮어쓰면 안 된다"


# ---------- NewsArticle 하위호환(design/20 Phase 5 체크리스트 2) ----------

def test_news_article_from_dict_backward_compatible_without_new_fields():
    old_dict = {"title": "t", "link": "http://x/1", "source": "s", "categories": ["macro"]}
    a = NewsArticle.from_dict(old_dict)
    assert a.level == "L1"
    assert a.impact_tags == []
    assert a.first_seen_at is None


def test_news_article_to_dict_round_trip_with_new_fields():
    a = _article(categories=["macro"])
    a.level = "L3"
    a.impact_tags = [{"ticker": "005930", "name": "삼성전자", "market": "KRX"}]
    a.first_seen_at = "2026-07-20T00:00:00+00:00"
    restored = NewsArticle.from_dict(a.to_dict())
    assert restored.level == "L3"
    assert restored.impact_tags == a.impact_tags
    assert restored.first_seen_at == a.first_seen_at
