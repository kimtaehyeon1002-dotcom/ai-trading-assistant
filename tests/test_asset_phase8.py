"""Phase 8 Asset — 지표 계산·정규화·스냅샷·암호화 발행(design/08, design/20 Phase 8)."""
from __future__ import annotations

from calculators.asset_indicators import (
    covered_roles,
    currency_exposure,
    goal_progress_pct,
    total_assets,
    with_weights,
)
from repositories import asset_repository, asset_snapshot_repository
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


def test_total_assets_none_when_every_account_missing():
    """결측은 0이 아니라 '모름' — 0을 돌려주면 총자산 ₩0이 사실처럼 렌더된다."""
    assert total_assets([_acct("a", None), _acct("b", None)]) is None


def test_covered_roles_splits_present_and_missing():
    covered, missing = covered_roles([_acct("a", 100.0), _acct("b", None)])
    assert covered == ["a"]
    assert missing == ["b"]


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
        {"종목코드": "A005930", "종목명": "삼성전자", "보유수량": "10", "매입가": "250,000",
         "현재가": "259,000", "평가금액": "2,590,000", "평가손익": "90,000", "수익률": "3.60"},
    ]}
    acct = asset_repository.build_kiwoom_account(raw, prev_krw=None)
    holding = acct["holdings"][0]
    assert holding["code"] == "005930"  # KOA 종목번호의 접두 'A' 제거
    assert holding["name"] == "삼성전자"
    assert holding["quantity"] == 10.0
    assert holding["avg_price"] == 250_000.0
    assert holding["price"] == 259_000.0
    assert holding["value_krw"] == 2_590_000.0
    assert holding["eval_pnl_krw"] == 90_000.0
    assert holding["pnl_pct"] == 3.60
    assert holding["weight_pct"] == 100.0  # 단일 종목 = 계좌 내 비중 100%


def test_kiwoom_holding_pnl_pct_derived_when_absent():
    """수익률 필드가 비면 평가금액−손익(=원가)에서 파생한다 — 빈칸 대신 사실 기반 계산."""
    raw = {"summary": {}, "holdings": [
        {"종목코드": "005930", "종목명": "삼성전자", "평가금액": "110", "평가손익": "10"},
    ]}
    acct = asset_repository.build_kiwoom_account(raw, prev_krw=None)
    assert acct["holdings"][0]["pnl_pct"] == 10.0


def test_build_kiwoom_account_principal_and_deposit():
    raw = {"summary": {"총평가금액": "84,120,000", "총평가손익금액": "9,340,000",
                       "총매입금액": "74,780,000", "예수금": "4,182,300"}}
    acct = asset_repository.build_kiwoom_account(raw, prev_krw=None)
    assert acct["principal_krw"] == 74_780_000.0
    assert acct["deposit_krw"] == 4_182_300.0


def test_principal_falls_back_to_balance_minus_pnl():
    """매입금액을 안 주는 계좌(ISA 등)도 투입원금 열이 비지 않게 한다."""
    acct = asset_repository.build_kis_isa_account(
        {"krw_value": 110.0, "eval_pnl_krw": 10.0}, prev_krw=None)
    assert acct["principal_krw"] == 100.0
    assert acct["eval_pnl_pct"] == 10.0


def test_build_bybit_account_holdings_from_coins():
    raw = {"total_equity_usd": 100.0, "coins": [
        {"coin": "USDT", "wallet_balance": 50.0, "usd_value": 30.0},
        {"coin": "BTC", "wallet_balance": 0.001, "usd_value": 70.0},
    ]}
    acct = asset_repository.build_bybit_account(raw, usdkrw=1378.50, prev_krw=None)
    usdt, btc = acct["holdings"]
    assert (usdt["code"], usdt["value_usd"], usdt["weight_pct"]) == ("USDT", 30.0, 30.0)
    assert (btc["code"], btc["value_usd"], btc["weight_pct"]) == ("BTC", 70.0, 70.0)
    assert btc["eval_pnl_krw"] is None  # Bybit는 평가손익 미제공 — 만들지 않는다


def test_total_pnl_sums_only_accounts_with_principal():
    accounts = [
        {"role": "a", "balance_krw": 110.0, "eval_pnl_krw": 10.0, "principal_krw": 100.0},
        {"role": "b", "balance_krw": 50.0, "eval_pnl_krw": None, "principal_krw": None},
    ]
    from calculators.asset_indicators import total_pnl
    assert total_pnl(accounts) == (10.0, 10.0, 100.0)


def test_total_pnl_none_when_no_account_reports_principal():
    from calculators.asset_indicators import total_pnl
    assert total_pnl([{"role": "a", "balance_krw": 50.0}]) == (None, None, None)


# ---------- repositories/asset_repository.py — payload + 암호화 발행 ----------

def test_persist_encrypted_skips_without_passphrase(monkeypatch, tmp_path):
    monkeypatch.setattr(asset_repository, "ASSET_PASSPHRASE", "")
    assert asset_repository.persist_encrypted({"x": 1}) is False
    assert not (tmp_path / "assets.enc.json").exists()


def test_persist_encrypted_skips_when_no_account_covered(monkeypatch, tmp_path):
    """4계좌 전부 결측이면 발행하지 않는다 — 직전 정상 발행물을 결측 봉투로 덮지 않기 위함."""
    monkeypatch.setattr(asset_repository, "ASSET_PASSPHRASE", "test-pass")
    monkeypatch.setattr(asset_repository, "DOCS_DIR", tmp_path)
    payload = asset_repository.build_payload([_acct("kiwoom", None), _acct("bybit", None)])
    assert payload["total_assets_krw"] is None
    assert asset_repository.persist_encrypted(payload) is False
    assert not (tmp_path / "data" / "asset" / "assets.enc.json").exists()


def test_build_payload_suppresses_derived_values_when_partially_missing(monkeypatch):
    """부분 결측 합계로 전일 대비·목표 달성률을 계산하면 결측이 자산 급락으로 둔갑한다."""
    monkeypatch.setattr(asset_repository, "ASSET_GOAL_KRW", 250_000_000.0)
    monkeypatch.setattr(asset_snapshot_repository, "previous_snapshot",
                        lambda: {"date": "2026-07-24", "total_assets_krw": 160_000_000.0})
    payload = asset_repository.build_payload([_acct("kiwoom", 84_120_000.0), _acct("bybit", None)])
    assert payload["missing_roles"] == ["bybit"]
    assert payload["day_change_pct"] is None
    assert payload["goal_progress_pct"] is None


def test_build_payload_computes_derived_values_when_complete(monkeypatch):
    monkeypatch.setattr(asset_repository, "ASSET_GOAL_KRW", 250_000_000.0)
    monkeypatch.setattr(asset_snapshot_repository, "previous_snapshot",
                        lambda: {"date": "2026-07-24", "total_assets_krw": 100_000_000.0})
    payload = asset_repository.build_payload([_acct("kiwoom", 101_000_000.0)])
    assert payload["missing_roles"] == []
    assert payload["day_change_pct"] == 1.0
    assert payload["goal_progress_pct"] == 40.4


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
