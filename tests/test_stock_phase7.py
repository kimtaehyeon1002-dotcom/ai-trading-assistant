"""Phase 7 Stock 랭킹(KR/US TOP30) — 정렬·검증·유니버스 병합·스키마(design/20 Phase 7)."""
from __future__ import annotations

from calculators.ranking_calculator import top_n
from config.themes import THEMES
from repositories import stock_repository
from tests.conftest import validator_for
from validators import ranking_validator


def _row(code, name, market, amount, close=100.0):
    return {"code": code, "name": name, "market": market, "close": close,
            "change_pct": 1.0, "volume": 1000, "amount": amount, "marcap": None}


# ---------- calculators/ranking_calculator.py ----------

def test_top_n_sorts_by_amount_descending_and_assigns_rank():
    rows = [_row("A", "A사", "KOSPI", 100), _row("B", "B사", "KOSPI", 300), _row("C", "C사", "KOSPI", 200)]
    ranked = top_n(rows, 2)
    assert [r["code"] for r in ranked] == ["B", "C"]
    assert [r["rank"] for r in ranked] == [1, 2]


def test_top_n_tags_known_theme_stock():
    ranked = top_n([_row("005930", "삼성전자", "KOSPI", 100)], 1)
    assert ranked[0]["theme"] == "반도체"


def test_top_n_leaves_theme_none_for_unmapped_stock():
    ranked = top_n([_row("999999", "무명주", "KOSPI", 100)], 1)
    assert ranked[0]["theme"] is None


def test_top_n_does_not_mutate_input_rows():
    rows = [_row("A", "A사", "KOSPI", 100)]
    top_n(rows, 1)
    assert "rank" not in rows[0]


# ---------- validators/ranking_validator.py ----------

def test_validator_rejects_none_and_short_lists():
    assert ranking_validator.validate(None) is None
    assert ranking_validator.validate([_row("A", "A", "KOSPI", 1)]) is None  # MIN_ROWS 미달


def test_validator_drops_bad_rows_but_keeps_valid(monkeypatch):
    monkeypatch.setattr(ranking_validator, "MIN_ROWS", 2)
    rows = [_row("A", "A", "KOSPI", 100), {"code": "", "close": 1, "amount": 1}, _row("B", "B", "KOSPI", 200)]
    out = ranking_validator.validate(rows)
    assert out is not None and len(out) == 2


# ---------- repositories/stock_repository.py ----------

def test_build_returns_none_table_when_collector_failed():
    body = stock_repository.build(None, [_row("A", "A", "KOSPI", 100)] * 30)
    assert body["kr"] is None
    assert body["us"] is not None


def test_build_matches_rankings_schema(schema_registry):
    kr_rows = [_row(f"{i:06d}", f"종목{i}", "KOSPI", 1000 - i) for i in range(35)]
    us_rows = [_row(f"T{i}", f"Ticker{i}", "US", 1000 - i) for i in range(35)]
    body = stock_repository.build(kr_rows, us_rows)
    v = validator_for("rankings.schema.json", schema_registry)
    errors = list(v.iter_errors(body))
    assert errors == [], [e.message for e in errors]
    assert len(body["kr"]["rows"]) == 30
    assert body["kr"]["population"] == 35


def test_build_universe_merges_top30_theme_and_watchlist_dedup():
    kr_rows = [_row("005930", "삼성전자", "KOSPI", 100)]  # 반도체 테마와 중복
    us_rows = [_row("NVDA", "NVIDIA", "US", 100)]  # 반도체 테마와 중복
    watchlist = [{"티커": "123456", "시장": "KOSDAQ"}]
    universe = stock_repository.build_universe(kr_rows, us_rows, watchlist)
    codes = {c for c, _n, _m in universe}
    assert "005930" in codes and "NVDA" in codes and "123456" in codes
    total_theme_codes = sum(len(v) for v in THEMES.values())
    assert len(universe) < total_theme_codes + 3  # 삼성전자·NVDA 중복 제거 확인


def test_build_universe_handles_all_none():
    """수집 실패(kr/us/watchlist 전부 None)여도 예외 없이 테마 종목만으로 유니버스를 구성한다."""
    universe = stock_repository.build_universe(None, None, None)
    codes = {c for c, _n, _m in universe}
    assert "005930" in codes  # 테마(config/themes.py)의 삼성전자
    assert len(codes) == len(universe)  # 중복 없음(예: TSLA가 2차전지·자동차 테마에 모두 등장)
