"""시세 2소스 교차검증 + 등락률 sanity 상한(design/23 D).

P4의 본질은 "Yahoo 값이 맞는지 판단할 근거가 없다"였다 — 틀렸다는 증거도 맞다는 증거도
없이 단일 소스를 그대로 실었다. 여기서는 대조 결과가 값에 정직하게 반영되는지만 본다
(네트워크는 타지 않는다 — 대조 소스는 스텁으로 주입).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from collectors import market_collector
from config.markets import CROSS_CHECK_CODES, MAX_ABS_CHANGE_PCT
from validators.market_validator import validate as v_market

_NOW = datetime(2026, 7, 24, 6, 30, tzinfo=timezone(timedelta(hours=9)))


@pytest.fixture
def stub_fdr(monkeypatch):
    """대조 소스를 {code: (price, pct)} 스텁으로 교체하고 '설치됨'으로 만든다."""
    def _apply(table: dict[str, tuple[float | None, float | None]]):
        monkeypatch.setattr(market_collector, "_fdr_available", lambda: True)
        monkeypatch.setattr(market_collector, "_fdr_quote",
                            lambda code: table.get(code, (None, None)))
    return _apply


def _yahoo_entry(pct: float, price: float = 100.0) -> dict:
    return {"price": price, "change_pct": pct, "source": "yahoo"}


# ---------- 교차검증 판정 ----------

def test_matching_sources_marked_verified(stub_fdr):
    stub_fdr({"US500": (7408.3, -1.21)})
    out = {"sp500": _yahoo_entry(-1.21, 7408.3)}
    market_collector._cross_check(out)
    assert out["sp500"]["quality"] == "verified"


def test_small_gap_within_tolerance_still_verified(stub_fdr):
    """실측된 VIX 오차(0.40%p, 기준 종가 차이)는 정상 범위로 통과해야 한다."""
    stub_fdr({"VIX": (18.7, 12.38)})
    out = {"vix": _yahoo_entry(11.98, 18.7)}
    market_collector._cross_check(out)
    assert out["vix"]["quality"] == "verified"


def test_diverging_sources_marked_degraded_but_value_kept(stub_fdr):
    """불일치 시 값을 지우지 않는다 — 어느 쪽이 옳은지 여기서는 알 수 없기 때문."""
    stub_fdr({"KS11": (7096.89, 4.40)})
    out = {"kospi": _yahoo_entry(0.74, 6797.7)}
    market_collector._cross_check(out)
    assert out["kospi"]["quality"] == "degraded"
    assert out["kospi"]["change_pct"] == 0.74


def test_missing_yahoo_filled_from_cross_source(stub_fdr):
    """Yahoo 결측을 2차 소스 실제 값으로 채운다(추정이 아니라 다른 소스의 사실)."""
    stub_fdr({"IXIC": (25137.69, -2.15)})
    out: dict[str, dict | None] = {"nasdaq": None}
    market_collector._cross_check(out)
    assert out["nasdaq"]["price"] == 25137.69
    assert out["nasdaq"]["source"] == "finance-datareader"


def test_no_cross_source_leaves_unverified(stub_fdr):
    stub_fdr({})  # 대조 소스가 아무 값도 못 주는 상황
    out = {"dow": _yahoo_entry(-0.97, 51711.65)}
    market_collector._cross_check(out)
    assert out["dow"]["quality"] == "unverified"


def test_cross_check_skipped_when_source_unavailable(monkeypatch):
    """32비트 키움 venv(FinanceDataReader 없음)에서도 수집이 깨지지 않는다."""
    monkeypatch.setattr(market_collector, "_fdr_available", lambda: False)
    out = {"sp500": _yahoo_entry(-1.21)}
    market_collector._cross_check(out)
    assert "quality" not in out["sp500"]  # 판정 자체를 하지 않음(= unverified로 흘러감)


def test_cross_check_codes_are_registered_symbols():
    from config.markets import ENVELOPE_META
    for key in CROSS_CHECK_CODES:
        assert key in ENVELOPE_META, f"{key}가 ENVELOPE_META에 없음"


# ---------- 등락률 sanity 상한 ----------

def test_absurd_change_pct_dropped():
    """자릿수 밀림(예: ×10)은 소스 오류 — 지수 상한 25%를 넘으면 폐기."""
    out = v_market({"sp500": {"price": 7408.3, "change_pct": 121.0, "source": "yahoo"}}, now=_NOW)
    assert out["sp500"] is None


def test_extreme_but_real_crash_survives():
    """1987 다우(-22.6%)급 실제 폭락은 통과해야 한다 — 그날이야말로 봐야 하는 날이다."""
    out = v_market({"dow": {"price": 40000.0, "change_pct": -22.6, "source": "yahoo"}}, now=_NOW)
    assert out["dow"] is not None


def test_vix_allows_much_larger_swings_than_indices():
    """VIX는 하루 두 자릿수 급등이 정상 — 지수와 같은 상한을 쓰면 실제 값이 사라진다."""
    assert MAX_ABS_CHANGE_PCT["vix"] > MAX_ABS_CHANGE_PCT["sp500"]
    out = v_market({"vix": {"price": 36.0, "change_pct": 115.0, "source": "yahoo"}}, now=_NOW)
    assert out["vix"] is not None


def test_fx_bound_is_tight():
    """환율 15% 일간 변동은 정상 시장에서 나오지 않는다 — 소스 오류로 본다."""
    out = v_market({"usdkrw": {"price": 1380.0, "change_pct": 15.0, "source": "x"}}, now=_NOW)
    assert out["usdkrw"] is None


def test_quality_flows_into_envelope():
    from repositories.market_repository import to_envelope_dict, to_quotes

    validated = {"sp500": {"price": 7408.3, "change_pct": -1.21,
                           "source": "yahoo", "quality": "degraded"}}
    body = to_envelope_dict(to_quotes(validated))
    assert body["sp500"]["quality"] == "degraded"


def test_quality_defaults_to_unverified():
    from repositories.market_repository import to_envelope_dict, to_quotes

    body = to_envelope_dict(to_quotes({"gold": {"price": 4052.8, "change_pct": -1.81,
                                                "source": "yahoo"}}))
    assert body["gold"]["quality"] == "unverified"


# ---------- 기준 시각 표시(design/23 P5) ----------

def test_live_quote_has_displayable_as_of():
    """라이브 수집분(as_of 필드 없음)도 화면에 보여줄 기준 시각을 갖는다.

    종전에는 캐시 경유 값만 as_of가 채워지고 라이브 값은 빈 문자열이라, 화면에서
    "이 숫자가 언제 것인지"를 확인할 방법이 없었다.
    """
    from repositories.market_repository import to_quotes

    q = to_quotes({"sp500": {"price": 7408.3, "change_pct": -1.21, "source": "yahoo"}})["sp500"]
    assert q.as_of, "라이브 수집분의 표시용 as_of가 비어 있다"


def test_as_of_display_matches_as_of_iso():
    """표시용 as_of와 판정용 as_of_iso가 다른 시각을 가리키면 배지와 글자가 서로 어긋난다."""
    from repositories.market_repository import to_quotes

    iso = "2026-07-24T04:40:00+00:00"  # = KST 13:40
    q = to_quotes({"kospi_night": {"price": 1132.5, "change_pct": 1.7,
                                   "source": "kiwoom", "as_of": iso}})["kospi_night"]
    assert q.as_of_iso == iso
    assert q.as_of == "07-24 13:40"
