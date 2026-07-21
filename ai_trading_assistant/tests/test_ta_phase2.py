"""Phase 2 수직 슬라이스 파일럿(TA) — 계산·검증·Envelope 스키마·신선도 문턱 검증(design/20 Phase 2)."""
from __future__ import annotations

from calculators import ta_indicators as ta
from config.freshness import THRESHOLDS
from repositories import ta_repository
from validators import ta_validator
from tests.conftest import validator_for


def _rows(closes: list[float], start="2026-01-01") -> list[dict]:
    from datetime import date, timedelta
    d = date.fromisoformat(start)
    out = []
    for c in closes:
        out.append({"date": d.isoformat(), "close": c})
        d += timedelta(days=1)
    return out


# ---------- calculators/ta_indicators.py ----------

def test_rsi_all_gains_is_100():
    closes = [100.0 + i for i in range(20)]  # 매일 상승
    assert ta.rsi(closes, 14) == 100.0


def test_rsi_all_losses_is_0():
    closes = [100.0 - i for i in range(20)]  # 매일 하락
    assert ta.rsi(closes, 14) == 0.0


def test_rsi_insufficient_data_is_none():
    assert ta.rsi([100.0, 101.0], 14) is None


def test_sma_and_deviation_pct():
    closes = [10.0] * 19 + [30.0]  # 20일 평균 = 11.0, 마지막 종가 30.0
    ma = ta.sma(closes, 20)
    assert ma == 11.0
    assert ta.deviation_pct(30.0, ma) == round((30.0 / 11.0 - 1) * 100, 2)


def test_sma_insufficient_data_is_none():
    assert ta.sma([1.0, 2.0], 5) is None


def test_trend_label_up_down_flat():
    up = [100.0] * 61 + [110.0]  # +10% vs 60일 전
    down = [100.0] * 61 + [90.0]  # -10%
    flat = [100.0] * 61 + [101.0]  # +1%, 횡보 밴드 안
    assert ta.trend_label(up, 60) == "상승 유지"
    assert ta.trend_label(down, 60) == "하락 유지"
    assert ta.trend_label(flat, 60) == "횡보"


def test_rsi_label_thresholds():
    assert ta.rsi_label(75) == "과매수"
    assert ta.rsi_label(25) == "과매도"
    assert ta.rsi_label(50) == "중립"
    assert ta.rsi_label(None) == "—"


# ---------- validators/ta_validator.py ----------

def test_validator_rejects_short_series():
    assert ta_validator.validate(_rows([100.0] * 10)) is None


def test_validator_rejects_none_or_empty():
    assert ta_validator.validate(None) is None
    assert ta_validator.validate([]) is None


def test_validator_drops_nothing_valid_but_requires_min_length():
    rows = _rows([100.0 + i * 0.1 for i in range(61)])
    out = ta_validator.validate(rows)
    assert out is not None and len(out) == 61


def test_validator_rejects_bad_closes():
    rows = _rows([100.0] * 60) + [{"date": "2026-03-02", "close": float("nan")}]
    assert ta_validator.validate(rows) is None  # nan 하나 때문에 61개 미만으로 탈락


# ---------- repositories/ta_repository.py — Envelope 스키마 검증 ----------

def test_ta_repository_build_matches_container_schema(schema_registry):
    rows = _rows([2500.0 + (i % 7) * 3.1 for i in range(90)])
    body = ta_repository.build(rows)
    v = validator_for("ta_preview.schema.json", schema_registry)
    errors = list(v.iter_errors(body))
    assert errors == [], [e.message for e in errors]


def test_ta_repository_all_four_metrics_present_and_as_of_consistent():
    rows = _rows([2500.0 + (i % 5) for i in range(90)])
    body = ta_repository.build(rows)
    assert set(body.keys()) == {"close", "deviation_20d", "rsi_14", "trend_60d"}
    as_ofs = {v["as_of_iso"] for v in body.values()}
    assert len(as_ofs) == 1, "4개 지표는 동일 배치이므로 as_of_iso가 모두 같아야 한다"


def test_ta_repository_close_change_abs_derived_correctly():
    rows = _rows([100.0] * 89 + [105.0])
    body = ta_repository.build(rows)
    assert body["close"]["change_abs"] == 5.0
    assert body["close"]["change_pct"] == 5.0


def test_ta_repository_as_of_iso_uses_krx_close_time_not_build_time():
    rows = _rows([100.0] * 90, start="2026-02-01")
    body = ta_repository.build(rows)
    # 최신 봉 날짜(2026-02-01 + 89일) 15:30 KST = 06:30 UTC로 환산되어야 한다
    assert body["close"]["as_of_iso"].endswith("06:30:00+00:00")


def test_sparkline_svg_has_no_hex_and_handles_short_series():
    import re
    svg = ta_repository.sparkline_svg([100.0, 101.0, 99.0])
    assert re.search(r"#[0-9a-fA-F]{3,6}", svg) is None
    assert ta_repository.sparkline_svg([100.0]) == ""  # 점 1개는 선을 그릴 수 없음


# ---------- 신선도 문턱(config/freshness.py) — design/21 §6-2 실측표와 일치해야 함 ----------

def test_ta_eod_thresholds_match_21_realized_table():
    assert THRESHOLDS["ta_eod"] == (24 * 60, 72 * 60)


# ---------- freshness_meta 발행 ----------

def test_freshness_meta_reads_runlog_workers(tmp_path, monkeypatch):
    from generators import freshness_meta
    from utils.jsonio import load_json

    fake_docs = tmp_path / "docs"
    (fake_docs / "ai-office").mkdir(parents=True)
    (fake_docs / "ai-office" / "runlog.json").write_text(
        '{"workers": {"TA Analyst": {"status": "completed", "last_run": "2026-01-01T00:00:00+09:00", '
        '"items": 90, "duration_ms": 120}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(freshness_meta, "DOCS_DIR", fake_docs)
    freshness_meta.generate()

    out = load_json(fake_docs / "data" / "meta" / "freshness.json", default=None)
    assert out is not None
    assert out["sources"]["TA Analyst"]["status"] == "completed"
    assert out["sources"]["TA Analyst"]["expected_T_min"] == 24 * 60
    assert out["sources"]["TA Analyst"]["items"] == 90
