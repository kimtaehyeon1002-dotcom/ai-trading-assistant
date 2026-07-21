"""Phase 3 시세 유니버스 증분 확장 — Envelope 실데이터 검증(design/20 Phase 3)."""
from __future__ import annotations

from config.markets import ENVELOPE_META, EXTENDED_SYMBOLS
from repositories.market_repository import to_envelope_dict, to_quotes
from tests.conftest import validator_for

_NEW_KEYS = [key for key, _sym, _label in EXTENDED_SYMBOLS]


def test_extended_symbols_all_registered_in_envelope_meta():
    """21 §2-2 요구 심볼(확장분)이 전부 ENVELOPE_META에 등재되어 있어야 컨테이너 스키마를 채운다."""
    for key in _NEW_KEYS:
        assert key in ENVELOPE_META, f"{key}가 ENVELOPE_META에 없음"


def test_expanded_market_json_validates_against_container_schema(schema_registry):
    """8지표 + 확장 14심볼 = 22개, 전량 Envelope 스키마(컨테이너 경유) 통과해야 한다(DoD 1)."""
    validated = {
        "usdkrw": {"price": 1378.5, "change_pct": None, "source": "frankfurter(ECB)"},
        "wti": {"price": 82.49, "change_pct": 4.21, "source": "yahoo", "previous_close": 79.16},
        "nasdaq": {"price": 20412.5, "change_pct": 0.94, "source": "yahoo", "previous_close": 20222.6},
    }
    for key, _sym, _label in EXTENDED_SYMBOLS:
        validated[key] = {"price": 100.0, "change_pct": 1.0, "source": "yahoo", "previous_close": 99.0}

    quotes = to_quotes(validated)
    body = {"as_of": "2026-07-20T09:00:00+09:00", **to_envelope_dict(quotes)}

    v = validator_for("market.schema.json", schema_registry)
    errors = list(v.iter_errors(body))
    assert errors == [], [e.message for e in errors]
    assert set(body.keys()) - {"as_of"} == {"usdkrw", "wti", "nasdaq", *_NEW_KEYS}


def test_failed_symbol_becomes_none_not_fake_zero():
    """DoD 2 — 실패 심볼은 None으로 강등되지 실제 산출물에서 0으로 채워지지 않는다."""
    validated = {"vix": None, "gold": {"price": 2350.0, "change_pct": 0.4, "source": "yahoo"}}
    quotes = to_quotes(validated)
    body = to_envelope_dict(quotes)
    assert body["vix"] is None
    assert body["vix"] != 0
    assert body["gold"]["value"] == 2350.0


def test_us10y_change_abs_is_percentage_point_delta():
    """DoD 3 — 미10Y의 change_abs가 채워진다(bp 환산은 표시 단계 책임, 값은 %p 델타로 정확해야 함).

    실측 확인(2026-07-20): yfinance fast_info.last_price는 이미 정규화된 수익률(%)을 반환하므로
    scale=1.0 — "수익률×10" 통설과 달리 배율 변환이 필요 없었다(config/markets.py 주석 참조).
    """
    validated = {"us10y": {"price": 4.541, "change_pct": -0.61, "source": "yahoo", "previous_close": 4.569}}
    quotes = to_quotes(validated)
    assert quotes["us10y"].price == 4.541
    assert round(quotes["us10y"].change_abs, 3) == round(4.541 - 4.569, 3)

    body = to_envelope_dict(quotes)
    assert body["us10y"]["unit"] == "%"
    assert body["us10y"]["change_abs"] is not None
    assert body["us10y"]["value"] == 4.541


def test_us10y_missing_previous_close_change_abs_is_none_not_wrong_number():
    validated = {"us10y": {"price": 4.541, "change_pct": None, "source": "yahoo"}}
    quotes = to_quotes(validated)
    assert quotes["us10y"].change_abs is None  # prev 없으면 억지 계산 금지


def test_scale_default_is_noop_for_existing_eight_symbols():
    """기존 8지표(scale=1.0)는 Phase 3 이후에도 값이 그대로 유지되어야 한다(회귀 방지)."""
    validated = {"nasdaq": {"price": 20412.5, "change_pct": 0.94, "source": "yahoo", "previous_close": 20222.6}}
    quotes = to_quotes(validated)
    assert quotes["nasdaq"].price == 20412.5
    assert quotes["nasdaq"].change_abs == 20412.5 - 20222.6


def test_all_extended_symbols_have_valid_session_key():
    valid = {"kr_regular", "kr_night", "us_regular", "globex", "fx", "crypto_24h", "none"}
    for key in _NEW_KEYS:
        _unit, session_key, _t, _scale = ENVELOPE_META[key]
        assert session_key in valid, f"{key}: 잘못된 session_key {session_key}"


def test_extended_symbol_names_registered():
    from repositories.market_repository import _NAMES
    for key, _sym, label in EXTENDED_SYMBOLS:
        assert _NAMES.get(key) == label
