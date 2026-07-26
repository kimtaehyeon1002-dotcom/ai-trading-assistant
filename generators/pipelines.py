"""공용 데이터 파이프라인 — collectors → validators → repositories → calculators.

morning/news 생성기가 공유(중복 제거). 각 단계는 runlog로 계측(AI Office의 사실 데이터).
collectors가 실행당 메모이즈하므로 한 실행에서 같은 데이터를 두 번 받지 않는다.
get_market()/get_news() 자신도 build.run_build() 1회 내에서는 결과를 메모이즈한다(검증/카테고리
분류/저장까지 재실행하면 낭비이므로) — 데스크톱 앱처럼 한 프로세스에서 run_build()를 여러 번
호출하는 경우를 위해 매 run_build() 시작 시 clear_cache()로 무효화한다.
"""
from __future__ import annotations

from calculators import news_categories
from collectors import kiwoom_collector, market_collector, news_collector
from models.market import Quote
from models.news import NewsArticle
from repositories import market_repository, news_repository
from utils import runlog
from validators import market_validator, news_validator

_cache: dict[str, object] = {}


def clear_cache() -> None:
    """run_build() 1회 시작 시 호출 — 이전 호출(같은 프로세스)의 메모이즈 결과를 폐기."""
    _cache.clear()


def get_market() -> dict[str, Quote | None]:
    """시장 8지표: 수집(yahoo/fx + kiwoom 캐시) → 검증 → Quote + market.json."""
    if "market" in _cache:
        return _cache["market"]

    def _collect() -> dict:
        return {**kiwoom_collector.collect(), **market_collector.collect()}

    raw = runlog.run_step("Data Officer", _collect, fallback={}) or {}
    validated = market_validator.validate(raw)
    quotes = market_repository.to_quotes(validated)
    market_repository.persist(quotes)
    _cache["market"] = quotes
    return quotes


def get_news() -> list[NewsArticle]:
    """뉴스: 수집 → 검증(중복/결측/타임스탬프) → 모델 병합 저장 → 카테고리 부여."""
    if "news" in _cache:
        return _cache["news"]
    raw = runlog.run_step("News Research", news_collector.collect, fallback=[]) or []
    validated = news_validator.validate(raw)
    merged = news_repository.merge_and_save(news_repository.to_articles(validated))
    result = news_categories.assign(merged)
    _cache["news"] = result
    return result
