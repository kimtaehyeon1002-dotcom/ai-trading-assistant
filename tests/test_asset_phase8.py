"""Phase 8 Asset — 지표 계산·정규화·스냅샷·암호화 발행(design/08, design/20 Phase 8)."""
from __future__ import annotations

from calculators.asset_indicators import currency_exposure, goal_progress_pct, total_assets, with_weights
from repositories import asset_repository
from utils.crypto import decrypt
from validators.asset_validator import parse_amount


def _acct(role, balance_krw, native="KRW"):
    return {"role": role, "label": role, "sub_label": "", "balance_krw": balance_krw, "native_currency": native}


# ---------- validators/asset_validator.py ----------

def test_parse_amount_handles_comma_string_and_none():
    assert parse_amount("1,234,567") == 1234567.0
    assert parse_amount(84120000) == 84120000.0
    assert parse_amount(None) is None
    assert parse_amount("") is None
    assert parse_amount("not-a-number") is None


# ---------- calculators/asset_indicators.py ----------

def test_total_assets_sums_present_balances_skips_none():
    accounts = [_acct("a", 100.0), _acct("b", None), _acct("c", 200.0)]
    assert total_assets(accounts) == 300.0


def test_with_weights_computed_against_total():
    accounts = [_acct("a", 300.0), _acct("b", 700.0)]
    out = with_weights(accounts)
    assert out[0]["weight_pct"] == 30.0
    assert out[1]["weight_pct"] == 70.0


def test_with_weights_none_when_total_zero():
    accounts = [_acct("a", None)]
    out = with_weights(accounts)
    assert out[0]["weight_pct"] is None


def test_goal_progress_pct_and_none_without_goal():
    assert goal_progress_pct(167_504_000, 250_000_000) == 67.0
    assert goal_progress_pct(100.0, None) is None
    assert goal_progress_pct(100.0, 0) is None


def test_currency_exposure_groups_by_native_currency():
    accounts = [_acct("a", 100.0, "KRW"), _acct("b", 100.0, "USD"), _acct("c", 300.0, "KRW")]
    exposure = currency_exposure(accounts)
    by_ccy = {e["currency"]: e["pct"] for e in exposure}
    assert by_ccy["KRW"] == 80.0
    assert by_ccy["USD"] == 20.0


# ---------- repositories/asset_repository.py — 계좌 정규화 ----------

def test_build_kiwoom_account_parses_korean_fields_and_day_change():
    raw = {"summary": {"총평가금액": "84,120,000", "총평가손익금액": "9,340,000", "총수익률": "12.49"}}
    acct = asset_repository.build_kiwoom_account(raw, prev_krw=83_378_000.0)
    assert acct["balance_krw"] == 84_120_000.0
    assert acct["eval_pnl_krw"] == 9_340_000.0
    assert acct["change_pct"] == round((84_120_000.0 / 83_378_000.0 - 1) * 100, 2)


def test_build_kiwoom_account_all_none_when_raw_missing():
    acct = asset_repository.build_kiwoom_account(None, prev_krw=None)
    assert acct["balance_krw"] is None
    assert acct["change_pct"] is None


def test_build_kis_foreign_account_converts_usd_to_krw():
    raw = {"usd_value": 12_845.20, "eval_pnl_usd": 1_500.0}
    acct = asset_repository.build_kis_foreign_account(raw, usdkrw=1378.50, prev_krw=None)
    assert acct["balance_krw"] == round(12_845.20 * 1378.50, 2)
    assert acct["fx_rate"] == 1378.50


def test_build_bybit_account_converts_usdt_to_krw():
    raw = {"total_equity_usd": 18_120.44}
    acct = asset_repository.build_bybit_account(raw, usdkrw=1378.50, prev_krw=None)
    assert acct["balance_krw"] == round(18_120.44 * 1378.50, 2)
    assert acct["native_currency"] == "USDT"


def test_build_kiwoom_account_normalizes_holdings():
    raw = {"summary": {}, "holdings": [
        {"종목코드": "005930", "종목명": "삼성전자", "보유수량": "10", "평가금액": "2,590,000", "평가손익": "90,000"},
    ]}
    acct = asset_repository.build_kiwoom_account(raw, prev_krw=None)
    assert acct["holdings"] == [
        {"code": "005930", "name": "삼성전자", "quantity": 10.0, "value_krw": 2_590_000.0, "eval_pnl_krw": 90_000.0},
    ]


def test_build_bybit_account_holdings_from_coins():
    raw = {"total_equity_usd": 100.0, "coins": [{"coin": "USDT", "wallet_balance": 50.0, "usd_value": 50.0}]}
    acct = asset_repository.build_bybit_account(raw, usdkrw=1378.50, prev_krw=None)
    assert acct["holdings"] == [{"code": "USDT", "name": "USDT", "quantity": 50.0, "value_usd": 50.0, "eval_pnl_krw": None}]


# ---------- repositories/asset_repository.py — payload + 암호화 발행 ----------

def test_persist_encrypted_skips_without_passphrase(monkeypatch, tmp_path):
    monkeypatch.setattr(asset_repository, "ASSET_PASSPHRASE", "")
    assert asset_repository.persist_encrypted({"x": 1}) is False
    assert not (tmp_path / "assets.enc.json").exists()


def test_persist_encrypted_writes_decryptable_envelope(monkeypatch, tmp_path):
    monkeypatch.setattr(asset_repository, "ASSET_PASSPHRASE", "test-pass")
    monkeypatch.setattr(asset_repository, "DOCS_DIR", tmp_path)
    payload = asset_repository.build_payload([_acct("kiwoom", 84_120_000.0)])
    ok = asset_repository.persist_encrypted(payload)
    assert ok is True
    import json
    envelope = json.loads((tmp_path / "data" / "asset" / "assets.enc.json").read_text(encoding="utf-8"))
    recovered = decrypt(envelope, "test-pass")
    assert recovered["total_assets_krw"] == 84_120_000.0
    assert recovered["accounts"][0]["weight_pct"] == 100.0
