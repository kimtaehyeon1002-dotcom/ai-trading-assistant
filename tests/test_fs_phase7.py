"""Phase 7 Financial Statements — 지표 계산·검증·조립·스키마(design/06, design/20 Phase 7)."""
from __future__ import annotations

from calculators import fs_indicators as fs
from repositories import fs_repository
from tests.conftest import validator_for
from validators import fs_validator


def _series(pairs):
    return [{"year": y, "value": v} for y, v in pairs]


def _financials(**overrides):
    base = {
        "revenue": _series([("2022", 100.0), ("2023", 110.0)]),
        "operating_income": _series([("2022", 10.0), ("2023", 12.0)]),
        "net_income": _series([("2022", 8.0), ("2023", 9.0)]),
        "assets": _series([("2022", 500.0), ("2023", 550.0)]),
        "liabilities": _series([("2022", 200.0), ("2023", 210.0)]),
        "equity": _series([("2022", 300.0), ("2023", 340.0)]),
        "operating_cf": _series([("2021", 15.0), ("2022", 18.0), ("2023", 20.0)]),
        "capex": _series([("2021", 5.0), ("2022", 6.0), ("2023", 7.0)]),
        "eps": _series([("2022", 2.0), ("2023", 2.2)]),
    }
    base.update(overrides)
    return base


# ---------- calculators/fs_indicators.py ----------

def test_revenue_growth_yoy_and_judgment():
    r = fs.revenue_growth(_financials())
    assert r["value"] == 10.0
    assert r["judgment"] == "good"


def test_revenue_growth_none_with_insufficient_data():
    assert fs.revenue_growth({"revenue": _series([("2023", 100.0)])}) is None


def test_revenue_growth_decline_is_caution():
    r = fs.revenue_growth(_financials(revenue=_series([("2022", 110.0), ("2023", 100.0)])))
    assert r["judgment"] == "caution"


def test_operating_margin_matches_years_and_own_avg():
    r = fs.operating_margin(_financials())
    y2022 = round(10.0 / 100 * 100, 2)
    y2023 = round(12.0 / 110 * 100, 2)
    assert r["value"] == y2023
    assert r["own_5y_avg"] == round((y2022 + y2023) / 2, 2)


def test_debt_ratio_absolute_thresholds():
    good = fs.debt_ratio(_financials(liabilities=_series([("2023", 50.0)]), equity=_series([("2023", 100.0)])))
    neutral = fs.debt_ratio(_financials(liabilities=_series([("2023", 150.0)]), equity=_series([("2023", 100.0)])))
    caution = fs.debt_ratio(_financials(liabilities=_series([("2023", 250.0)]), equity=_series([("2023", 100.0)])))
    assert good["judgment"] == "good"
    assert neutral["judgment"] == "neutral"
    assert caution["judgment"] == "caution"


def test_free_cash_flow_good_when_all_recent_positive():
    r = fs.free_cash_flow(_financials())
    assert r["value"] == 20.0 - 7.0
    assert r["judgment"] == "good"


def test_free_cash_flow_caution_when_latest_negative():
    r = fs.free_cash_flow(_financials(operating_cf=_series([("2022", 18.0), ("2023", 5.0)]),
                                       capex=_series([("2022", 6.0), ("2023", 10.0)])))
    assert r["value"] == -5.0
    assert r["judgment"] == "caution"


def test_valuation_per_computed_and_no_judgment_key():
    r = fs.valuation_per(_financials(), close_price=44.0)
    assert r["per"] == round(44.0 / 2.2, 2)
    assert "judgment" not in r


def test_valuation_per_none_without_close_price():
    assert fs.valuation_per(_financials(), None) is None


def test_valuation_per_negative_eps_flags_note():
    r = fs.valuation_per(_financials(eps=_series([("2023", -1.0)])), close_price=44.0)
    assert r["per"] is None
    assert r["note"]


# ---------- validators/fs_validator.py ----------

def test_fs_validator_drops_bad_rows_keeps_rest():
    raw = {"revenue": [{"year": "2023", "value": 100.0}, {"year": "", "value": 1.0}, {"year": "2022", "value": float("nan")}]}
    out = fs_validator.validate(raw)
    assert out["revenue"] == [{"year": "2023", "value": 100.0}]


def test_fs_validator_none_when_all_lines_empty():
    assert fs_validator.validate({"revenue": []}) is None
    assert fs_validator.validate(None) is None
    assert fs_validator.validate({}) is None


# ---------- repositories/fs_repository.py ----------

def test_build_all_none_when_financials_missing():
    body = fs_repository.build("005930", "삼성전자", "KOSPI", None, None, "dart")
    assert body["source"] == "none"
    assert all(body[k] is None for k in ("growth", "profitability", "stability", "cashflow", "valuation"))


def test_build_matches_schema(schema_registry):
    body = fs_repository.build("NVDA", "NVIDIA", "US", _financials(), 44.0, "edgar")
    v = validator_for("financials.schema.json", schema_registry)
    errors = list(v.iter_errors(body))
    assert errors == [], [e.message for e in errors]
