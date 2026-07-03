"""공용 데이터 파이프라인 — collectors → validators → repositories → calculators.

morning/news 생성기가 공유(중복 제거). 각 단계는 runlog로 계측(AI Office의 사실 데이터).
collectors가 실행당 메모이즈하므로 한 실행에서 같은 데이터를 두 번 받지 않는다.
"""
from __future__ import annotations

from calculators import news_categories
from collectors import kiwoom_collector, market_collector, news_collector
from models.market import Quote
from models.news import NewsArticle
from repositories import market_repository, news_repository
from utils import runlog
from validators import market_validator, news_validator


def get_market() -> dict[str, Quote | None]:
    """시장 8지표: 수집(yahoo/fx + kiwoom 캐시) → 검증 → Quote + market.json."""
    def _collect() -> dict:
        return {**kiwoom_collector.collect(), **market_collector.collect()}

    raw = runlog.run_step("Data Officer", _collect, fallback={}) or {}
    validated = market_validator.validate(raw)
    quotes = market_repository.to_quotes(validated)
    market_repository.persist(quotes)
    return quotes


def get_news() -> list[NewsArticle]:
    """뉴스: 수집 → 검증(중복/결측/타임스탬프) → 모델 병합 저장 → 카테고리 부여."""
    raw = runlog.run_step("News Research", news_collector.collect, fallback=[]) or []
    validated = news_validator.validate(raw)
    merged = news_repository.merge_and_save(news_repository.to_articles(validated))
    return news_categories.assign(merged)
