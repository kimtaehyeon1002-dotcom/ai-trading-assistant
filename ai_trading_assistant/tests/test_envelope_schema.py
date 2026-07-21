"""Phase 0 데이터 계약 — Envelope/컨테이너 스키마 및 repositories 직렬화 검증(design/20 Phase 0 DoD)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from models.market import Quote
from repositories.market_repository import to_envelope_dict, to_quotes

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _registry() -> Registry:
    resources = [(s["$id"], Resource.from_contents(s)) for s in (_load("envelope.schema.json"), _load("market.schema.json"))]
    return Registry().with_resources(resources)


def _market_validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(_load("market.schema.json"), registry=_registry())


def test_schema_files_are_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(_load("envelope.schema.json"))
    jsonschema.Draft202012Validator.check_schema(_load("market.schema.json"))


def test_persisted_market_json_shape_validates_against_container_schema():
    """실제 collect→validate 산출과 동일한 raw 형태에서 to_quotes→to_envelope_dict 결과가 스키마를 통과한다."""
    validated = {
        "nasdaq": {"price": 20412.5, "change_pct": 0.94, "source": "yahoo", "previous_close": 20222.6},
        "usdkrw": {"price": 1378.5, "change_pct": None, "source": "frankfurter(ECB)"},
        "kospi_night": {"price": 368.45, "change_pct": 0.42, "as_of": "2026-07-10T13:00:00+00:00", "source": "kiwoom"},
        "kosdaq_night": None,  # 검증 단계에서 이미 탈락(None)한 항목도 컨테이너 형태로 남는다
    }
    quotes = to_quotes(validated)
    body = {"as_of": "2026-07-10T22:00:00+09:00", **to_envelope_dict(quotes)}

    errors = list(_market_validator().iter_errors(body))
    assert errors == []


def test_surviving_items_have_non_null_as_of_iso_and_session_key():
    validated = {
        "sp500": {"price": 6214.85, "change_pct": 0.52, "source": "yahoo"},  # previous_close 없어도 통과해야 함
        "kospi_night": {"price": 368.45, "change_pct": 0.42, "as_of": "2026-07-10T13:00:00+00:00", "source": "kiwoom"},
        "unknown_symbol": {"price": 1.0, "change_pct": 0.0, "source": "x"},  # ENVELOPE_META 미등재 심볼도 커버
    }
    quotes = to_quotes(validated)
    for key, q in quotes.items():
        assert q is not None, key
        assert q.as_of_iso, f"{key}: as_of_iso must be non-null"
        assert q.session_key, f"{key}: session_key must be non-empty"

    body = to_envelope_dict(quotes)
    for key, env in body.items():
        assert env["as_of_iso"], key
        assert env["session_key"], key


def test_none_survives_as_container_null_not_dropped():
    body = to_envelope_dict({"kosdaq_night": None})
    assert body == {"kosdaq_night": None}


def test_change_abs_derived_from_previous_close_when_available():
    validated = {"dow": {"price": 44458.30, "change_pct": 0.49, "source": "yahoo", "previous_close": 44240.10}}
    quotes = to_quotes(validated)
    assert quotes["dow"].change_abs == 44458.30 - 44240.10


def test_change_abs_none_when_previous_close_absent():
    validated = {"usdkrw": {"price": 1378.5, "change_pct": None, "source": "frankfurter(ECB)"}}
    quotes = to_quotes(validated)
    assert quotes["usdkrw"].change_abs is None


def test_quote_construction_backward_compatible_without_new_fields():
    """신규 필드 없이 기존 방식대로 Quote를 만들어도 여전히 동작한다(하위호환)."""
    q = Quote(symbol="nasdaq", name="NASDAQ", price=100.0, change_pct=1.0, currency="USD", source="yahoo", as_of="")
    assert q.as_of_iso is None
    assert q.session_key == "none"
    assert q.change_abs is None
    assert q.ref_price is None
