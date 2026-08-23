"""Phase 6 Macroeconomics(독립 트랙) — YoY 계산·김치프리미엄·결측 문법·DST·스키마(design/20 Phase 6)."""
from __future__ import annotations

from calculators.macro_indicators import kimchi_premium_pct, yoy_change
from collectors import ecos_collector, fred_collector
from config.freshness import THRESHOLDS
from config.settings import TEMPLATES_DIR
from repositories import macro_repository
from tests.conftest import validator_for
from validators import macro_validator


def _obs(pairs):
    return [{"date": d, "value": v} for d, v in pairs]


# ---------- calculators/macro_indicators.py ----------

def test_yoy_change_matches_exact_12_months_prior():
    obs = _obs([
        ("2024-06-01", 100.0), ("2025-06-01", 103.0), ("2025-07-01", 104.0), ("2026-07-01", 108.0),
    ])
    result = yoy_change(obs)
    assert result is not None
    assert result["prior_date"] == "2025-07-01"
    assert result["change_abs"] == 4.0
    assert result["change_pct"] == round((108.0 / 104.0 - 1) * 100, 2)


def test_yoy_change_none_when_no_12_month_match():
    obs = _obs([("2026-05-01", 100.0), ("2026-07-01", 103.0)])
    assert yoy_change(obs) is None


def test_yoy_change_none_with_insufficient_data():
    assert yoy_change(_obs([("2026-07-01", 100.0)])) is None


def test_kimchi_premium_calculation():
    # BTC/USD=65000, USD/KRW=1400 → 환산 91,000,000. 실거래 92,000,000 → 프리미엄 약 +1.10%
    pct = kimchi_premium_pct(92_000_000, 65_000, 1400)
    assert pct == round((92_000_000 / (65_000 * 1400) - 1) * 100, 2)


def test_kimchi_premium_none_when_any_input_missing():
    assert kimchi_premium_pct(None, 65_000, 1400) is None
    assert kimchi_premium_pct(92_000_000, None, 1400) is None
    assert kimchi_premium_pct(92_000_000, 65_000, None) is None


# ---------- collectors — 키 미설정 시 정직한 skip ----------

def test_fred_collect_returns_all_none_without_key(monkeypatch):
    monkeypatch.setattr("config.settings.FRED_API_KEY", "")
    monkeypatch.setattr(fred_collector, "FRED_API_KEY", "")
    result = fred_collector.collect()
    assert all(v is None for v in result.values())
    assert set(result.keys()) == {sid for sid, _ in fred_collector.SERIES}


def test_ecos_collect_none_without_key(monkeypatch):
    monkeypatch.setattr(ecos_collector, "ECOS_API_KEY", "")
    assert ecos_collector.collect() is None


# ---------- validators/macro_validator.py ----------

def test_validator_rejects_short_or_bad_observations():
    assert macro_validator.validate_observations(None) is None
    assert macro_validator.validate_observations([]) is None
    assert macro_validator.validate_observations([{"date": "2026-01-01", "value": 1.0}]) is None  # 1개뿐


def test_validator_drops_non_finite_but_keeps_rest():
    rows = [
        {"date": "2026-01-01", "value": 1.0},
        {"date": "2026-02-01", "value": float("nan")},
        {"date": "2026-03-01", "value": 2.0},
    ]
    out = macro_validator.validate_observations(rows)
    assert out is not None and len(out) == 2


# ---------- repositories/macro_repository.py — Envelope/컨테이너 스키마 ----------

def test_build_indicators_matches_container_schema(schema_registry):
    fred_data = {
        "CPIAUCSL": {
            "observations": _obs([(f"2024-{m:02d}-01", 100 + m) for m in range(1, 13)] + [("2025-07-01", 115.0), ("2026-07-01", 118.0)]),
            "next_release": "2026-08-12",
        },
        "PCEPI": None, "GDP": None, "UNRATE": None, "PAYEMS": None,
    }
    indicators = macro_repository.build_indicators(fred_data)
    indicators["BOK_BASE_RATE"] = macro_repository.build_base_rate({"base_rate": _obs([("202505", 3.0), ("202506", 3.25)])})
    indicators["BTC_KRW"] = macro_repository.build_btc(
        {"price": 92_000_000.0, "change_pct": 1.1, "previous_close": 91_000_000.0},
        {"btc": None, "usdkrw": None},
    )
    v = validator_for("macro_indicators.schema.json", schema_registry)
    errors = list(v.iter_errors(indicators))
    assert errors == [], [e.message for e in errors]


def test_build_indicators_none_when_missing_not_fake_zero():
    indicators = macro_repository.build_indicators({sid: None for sid, _ in fred_collector.SERIES})
    assert all(v is None for v in indicators.values())
    assert 0 not in indicators.values()


def test_consensus_key_omitted_when_not_configured(monkeypatch):
    from config import consensus as consensus_mod
    monkeypatch.setattr(consensus_mod, "CONSENSUS", {})
    monkeypatch.setattr(macro_repository, "CONSENSUS", {})
    fred_data = {"CPIAUCSL": {"observations": _obs([("2026-06-01", 100.0), ("2026-07-01", 101.0)]), "next_release": None}}
    fred_data.update({sid: None for sid, _ in fred_collector.SERIES if sid != "CPIAUCSL"})
    indicators = macro_repository.build_indicators(fred_data)
    assert "consensus" not in indicators["CPIAUCSL"]  # 미입력 시 키 자체가 없어야 한다(빈칸 렌더 금지)


def test_calendar_matches_schema_and_dst_offsets_are_correct(schema_registry):
    calendar = macro_repository.build_calendar({sid: None for sid, _ in fred_collector.SERIES})
    v = validator_for("macro_calendar.schema.json", schema_registry)
    errors = list(v.iter_errors(calendar))
    assert errors == [], [e.message for e in errors]

    by_date = {e["date"]: e for e in calendar["events"]}
    # 1월(EST, UTC-5): 14:00 ET → 19:00 UTC / 7월(EDT, UTC-4): 14:00 ET → 18:00 UTC
    assert by_date["2026-01-28"]["event_at_utc"].endswith("19:00:00+00:00")
    assert by_date["2026-07-29"]["event_at_utc"].endswith("18:00:00+00:00")


def test_macro_threshold_matches_21_realized_table():
    assert THRESHOLDS["macro"] == (120, 180)

# ---------- ECOS 다항목 통계표 회귀(2026-08-14 실호출로 드러난 결함) ----------

def _ecos_row(item_code: str, time: str, value: str) -> dict:
    return {"STAT_CODE": "722Y001", "ITEM_CODE1": item_code, "TIME": time, "DATA_VALUE": value}


def test_ecos_url_pins_item_code_to_base_rate(monkeypatch):
    """722Y001은 기준금리 단일 계열이 아니다 — 항목코드를 URL에 박지 않으면 다른 금리가 섞여 온다."""
    seen = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"StatisticSearch": {"row": [_ecos_row("0101000", "202607", "2.75")]}}

    def _fake_get(url, **kw):
        seen["url"] = url
        return _Resp()

    monkeypatch.setattr(ecos_collector, "ECOS_API_KEY", "TESTKEY")
    monkeypatch.setattr("requests.get", _fake_get)
    ecos_collector.collect_base_rate("202408", "202608")
    assert seen["url"].endswith(f"/{ecos_collector.BASE_RATE_ITEM_CODE}")


def test_ecos_filters_out_other_items_instead_of_publishing_wrong_rate(monkeypatch):
    """항목이 섞여 와도 기준금리만 남아야 한다 — 이 방어가 없어서 1.75%가 발행될 뻔했다."""
    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"StatisticSearch": {"row": [
                _ecos_row("0101000", "202606", "2.5"),
                _ecos_row("0102000", "202606", "2.4"),   # 자금조정예금금리 — 섞여 오는 다른 항목
                _ecos_row("0104000", "202606", "4.0"),
                _ecos_row("0101000", "202607", "2.75"),
                _ecos_row("0107000", "202607", "1.75"),  # 종전 코드가 "기준금리"로 발행하던 값
            ]}}

    monkeypatch.setattr(ecos_collector, "ECOS_API_KEY", "TESTKEY")
    monkeypatch.setattr("requests.get", lambda url, **kw: _Resp())
    obs = ecos_collector.collect_base_rate("202408", "202608")
    assert obs == [{"date": "202606", "value": 2.5}, {"date": "202607", "value": 2.75}]
    assert obs[-1]["value"] != 1.75


# ---------- 컨센서스 필드명 계약(config ↔ 템플릿) ----------

def test_consensus_block_renders_value_and_omits_malformed_entries():
    """config의 필드명이 템플릿과 어긋나면 줄 자체가 생략돼야 한다 — 숫자 없는 "예상  (…)" 금지."""
    import re

    from generators.base import _env

    src = (TEMPLATES_DIR / "pages" / "macro.html").read_text(encoding="utf-8")
    block = re.search(r"\{% if item\.consensus.*?\{% endif %\}", src, re.S)
    assert block, "macro.html에서 consensus 블록을 찾지 못했다(템플릿 구조 변경?)"
    tpl = _env.from_string(block.group(0))

    ok = tpl.render(item={"consensus": {"value": 3.1, "as_of": "2026-07-15"}})
    assert "3.1" in ok and "2026-07-15" in ok

    # 옛 독스트링 형식("consensus" 키) · 값이 None · 항목 없음 → 전부 렌더되지 않는다
    for bad in ({"consensus": 3.1, "as_of": "2026-07-15"}, {"value": None, "as_of": "2026-07-15"}, None):
        assert tpl.render(item={"consensus": bad}).strip() == ""
