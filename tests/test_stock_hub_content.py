"""Stock Hub 콘텐츠 — 관련뉴스·시장일정(design/04 §3-5 D·E).

실제 사고 재현: 관련종목 태깅을 뉴스 **생성기**가 저장 뒤에 붙여서 저장소의 impact_tags가
늘 비어 있었고, 그 저장소를 읽는 get_stock()이 Hub의 "관련 뉴스"를 **전 종목 0건**으로
발행했다(실측 191개 전부 0건). 뉴스 페이지만 보면 태그가 정상이라 드러나지 않았다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from calculators import news_entities
from models.news import NewsArticle
from repositories import stock_repository

_UNIVERSE = [("005930", "삼성전자", "KOSPI"), ("NVDA", "NVIDIA", "NASDAQ")]


def _article(title, link="http://x/1", summary="", **kw):
    return NewsArticle(title=title, link=link, summary=summary,
                       published=datetime.now(timezone.utc), **kw)


def _hub(articles, calendar_events=None):
    news_entities.assign(articles)
    return stock_repository.build_hub_entries(
        None, None, _UNIVERSE, None, articles, calendar_events=calendar_events)


# ---------- 관련 뉴스 ----------

def test_related_news_reaches_hub():
    hub = _hub([_article("삼성전자 HBM4 양산 개시")])
    assert len(hub["005930"]["related_news"]) == 1
    assert hub["NVDA"]["related_news"] == []


def test_untagged_articles_produce_no_related_news():
    """태깅이 안 된 기사는 어느 종목에도 붙지 않는다 — 이게 191개 전부 0건이던 상태다."""
    a = _article("삼성전자 HBM4 양산 개시")
    # assign을 부르지 않음 = 저장소에서 impact_tags가 비어 있던 실제 상황
    hub = stock_repository.build_hub_entries(None, None, _UNIVERSE, None, [a])
    assert hub["005930"]["related_news"] == []


def test_hub_uses_translated_title():
    """뉴스 페이지는 번역본, Hub는 원문이면 같은 기사가 화면마다 다른 언어로 보인다."""
    a = _article("Nvidia unveils new GPU", title_ko="엔비디아, 신형 GPU 공개", lang="en")
    hub = _hub([a])
    assert hub["NVDA"]["related_news"][0]["title"] == "엔비디아, 신형 GPU 공개"


def test_english_article_matches_korean_company():
    """수집원 절반이 영문 매체다 — "Samsung Electronics"를 못 잡으면 국내 대형주가 늘 빈다."""
    hub = _hub([_article("Samsung Electronics raises HBM output")])
    assert len(hub["005930"]["related_news"]) == 1


def test_korean_article_matches_us_company():
    hub = _hub([_article("엔비디아 실적 호조")])
    assert len(hub["NVDA"]["related_news"]) == 1


def test_related_news_capped_at_five():
    arts = [_article(f"삼성전자 소식 {i}", link=f"http://x/{i}") for i in range(9)]
    assert len(_hub(arts)["005930"]["related_news"]) == 5


# ---------- 시장 일정 ----------

def _event(days: int, label="FOMC 금리 결정"):
    when = datetime.now(timezone.utc) + timedelta(days=days)
    return {"date": when.strftime("%Y-%m-%d"), "label": label,
            "source": "fomc", "event_at_utc": when.isoformat()}


def test_only_upcoming_events_are_shown():
    """지나간 일정을 '다가오는 일정'에 실으면 그 블록 전체를 못 믿게 된다."""
    out = stock_repository.upcoming_market_events([_event(-10, "지난 회의"), _event(5)])
    assert [e["label"] for e in out] == ["FOMC 금리 결정"]


def test_events_are_sorted_by_time_and_capped():
    events = [_event(30, "셋째"), _event(5, "첫째"), _event(10, "둘째"), _event(60, "넷째"),
              _event(90, "다섯째")]
    out = stock_repository.upcoming_market_events(events, limit=4)
    assert [e["label"] for e in out] == ["첫째", "둘째", "셋째", "넷째"]


def test_malformed_events_are_skipped_not_crash():
    out = stock_repository.upcoming_market_events(
        [{"label": "시각 없음"}, {"event_at_utc": "쓰레기", "label": "파싱실패"}, _event(3)])
    assert len(out) == 1


def test_no_events_yields_empty_not_fabricated():
    assert stock_repository.upcoming_market_events(None) == []
    assert stock_repository.upcoming_market_events([]) == []


def test_market_events_attached_to_every_hub_entry():
    hub = _hub([], calendar_events=[_event(5)])
    for code in ("005930", "NVDA"):
        assert len(hub[code]["market_events"]) == 1
        assert hub[code]["market_events"][0]["label"] == "FOMC 금리 결정"


# ---------- 파이프라인 순서(회귀 방지) ----------

def test_pipeline_tags_articles_before_saving_them():
    """저장 전에 태깅해야 저장소를 읽는 Stock Hub가 태그를 본다.

    순서가 뒤집히면 뉴스 페이지는 멀쩡한데 Hub만 조용히 비는, 발견이 매우 늦는 결함이 된다.
    """
    import inspect

    from generators import pipelines

    src = inspect.getsource(pipelines.get_news)
    assert src.index("news_entities.assign") < src.index("news_repository.save"), \
        "태깅이 저장보다 뒤에 있다 — Stock Hub 관련뉴스가 전 종목 0건이 된다"
