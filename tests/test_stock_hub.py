"""Stock Hub 패널 데이터(design/05, design/20 Phase 7) — 시세 병합·TradingView 심볼·스키마."""
from __future__ import annotations

from datetime import datetime, timezone

from models.news import NewsArticle
from repositories import stock_repository
from tests.conftest import validator_for


def _kr_row(code, name, amount=100.0):
    return {"code": code, "name": name, "market": "KOSPI", "close": 1000.0,
            "change_pct": 1.0, "volume": 10, "amount": amount, "marcap": 999.0}


def _us_row(code, name, amount=100.0):
    return {"code": code, "name": name, "market": "US", "close": 50.0,
            "change_pct": -1.0, "volume": 20, "amount": amount, "marcap": None}


def _article(ticker):
    a = NewsArticle(title="테스트 기사", link="https://example.com/a", source="테스트",
                     published=datetime.now(timezone.utc))
    a.impact_tags = [{"ticker": ticker, "name": "x", "market": "KRX"}]
    return a


def test_tradingview_symbol_kr_uses_krx_prefix():
    assert stock_repository._tradingview_symbol("005930", "KOSPI") == "KRX:005930"
    assert stock_repository._tradingview_symbol("035720", "KRX") == "KRX:035720"


def test_tradingview_symbol_us_uses_bare_ticker():
    assert stock_repository._tradingview_symbol("NVDA", "US") == "NVDA"


def test_build_hub_entries_quote_from_kr_full_listing_even_outside_top30():
    """KR은 전종목 스냅샷이라 TOP30 밖 테마 종목도 시세를 채울 수 있어야 한다."""
    kr_rows = [_kr_row("005930", "삼성전자")]
    universe = [("005930", "삼성전자", "KOSPI")]
    entries = stock_repository.build_hub_entries(kr_rows, None, universe, {}, [])
    assert entries["005930"]["quote"]["close"] == 1000.0
    assert entries["005930"]["theme"] == "반도체"


def test_build_hub_entries_missing_quote_is_none_not_fake():
    universe = [("999999", "무명주", "KOSPI")]
    entries = stock_repository.build_hub_entries(None, None, universe, {}, [])
    assert entries["999999"]["quote"] is None


def test_build_hub_entries_us_supplementary_quote_fills_gap():
    """S&P500 후보 밖 US 테마 종목(예: TSM)은 보조 조회 결과로 채운다."""
    universe = [("TSM", "TSMC", "NYSE")]
    supplementary = {"TSM": {"close": 400.0, "change_pct": 2.0, "volume": 100, "amount": 40000.0}}
    entries = stock_repository.build_hub_entries(None, None, universe, supplementary, [])
    assert entries["TSM"]["quote"]["close"] == 400.0


def test_build_hub_entries_related_news_filtered_by_ticker():
    universe = [("005930", "삼성전자", "KOSPI"), ("000660", "SK하이닉스", "KOSPI")]
    articles = [_article("005930"), _article("000660"), _article("000660")]
    entries = stock_repository.build_hub_entries(None, None, universe, {}, articles)
    assert len(entries["005930"]["related_news"]) == 1
    assert len(entries["000660"]["related_news"]) == 2


def test_build_hub_entries_matches_schema(schema_registry):
    kr_rows = [_kr_row("005930", "삼성전자")]
    universe = [("005930", "삼성전자", "KOSPI"), ("999999", "무명주", "KOSPI")]
    entries = stock_repository.build_hub_entries(kr_rows, None, universe, {}, [])
    v = validator_for("stock_hub.schema.json", schema_registry)
    for code, body in entries.items():
        errors = list(v.iter_errors(body))
        assert errors == [], (code, [e.message for e in errors])
