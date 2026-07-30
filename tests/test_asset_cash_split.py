"""design/25 §8 — 예수금/주식 분리와 손익률 스케일 사고 방지.

사용자가 겪은 두 결함을 회귀로 고정한다:
  ① 한투 위탁 총액에 외화예수금이 통째로 빠져 실제보다 14.8% 적게 표시됨
  ② 키움 총수익률이 -1718%로 표시됨(KOA가 100배 스케일로 주는 값을 그대로 사용)
"""
from __future__ import annotations

from repositories import asset_repository as ar


# ---------- ② 손익률: 절대금액에서 계산한다 ----------

def test_kiwoom_ignores_hundredfold_reported_rate():
    """-1718%로 보고돼도 화면에는 매입금액 기준으로 계산한 -17.18%가 나가야 한다."""
    raw = {"summary": {
        "총평가금액": "8,282,000", "총매입금액": "10,000,000",
        "총평가손익금액": "-1,718,000", "총수익률": "-1718", "예수금": "0",
    }, "holdings": []}
    acct = ar.build_kiwoom_account(raw, prev_krw=None)
    assert acct["eval_pnl_pct"] == -17.18


def test_rate_derived_from_pnl_when_purchase_amount_missing():
    """총매입금액이 없어도 원가는 '평가금액 − 손익'으로 유도된다 — 그 원가로 계산한다."""
    raw = {"summary": {"총평가금액": "1000", "총평가손익금액": "-100", "총수익률": "-1000"},
           "holdings": []}
    # 원가 1100 = 1000 − (−100) → −100/1100 = −9.09%. 보고값 −1000%는 채택하지 않는다.
    assert ar.build_kiwoom_account(raw, prev_krw=None)["eval_pnl_pct"] == -9.09


def test_rate_is_omitted_when_no_materials_at_all():
    """원가를 어떤 경로로도 못 구하면 결측 — 스케일 미검증 보고값을 대신 쓰지 않는다."""
    raw = {"summary": {"총평가손익금액": "-100", "총수익률": "-1718"}, "holdings": []}
    assert ar.build_kiwoom_account(raw, prev_krw=None)["eval_pnl_pct"] is None


def test_holding_rate_also_computed_from_cost():
    raw = {"summary": {}, "holdings": [{
        "종목코드": "A005930", "종목명": "삼성전자", "보유수량": "10",
        "매입가": "100000", "현재가": "90000", "평가금액": "900000",
        "평가손익": "-100000", "수익률": "-1000",  # 100배 스케일 보고값
    }]}
    holding = ar.build_kiwoom_account(raw, prev_krw=None)["holdings"][0]
    assert holding["pnl_pct"] == -10.0


def test_rate_matches_reported_when_scale_is_sane():
    """정상 스케일이면 계산값과 보고값이 같으므로 화면 값이 바뀌지 않는다(회귀 방지)."""
    raw = {"summary": {"총평가금액": "9,000,000", "총매입금액": "10,000,000",
                       "총평가손익금액": "-1,000,000", "총수익률": "-10.0"},
           "holdings": []}
    assert ar.build_kiwoom_account(raw, prev_krw=None)["eval_pnl_pct"] == -10.0


# ---------- ① 예수금/주식 분리 ----------

def test_kiwoom_adds_deposit_when_total_excludes_it():
    """총평가금액이 보유종목 합계와 같으면 유가증권만이라는 뜻 → 예수금을 더해야 총액이다."""
    raw = {"summary": {"총평가금액": "1,000,000", "예수금": "500,000"},
           "holdings": [{"종목코드": "A005930", "종목명": "삼성전자", "평가금액": "1,000,000"}]}
    acct = ar.build_kiwoom_account(raw, prev_krw=None)
    assert acct["securities_krw"] == 1_000_000.0
    assert acct["deposit_krw"] == 500_000.0
    assert acct["balance_krw"] == 1_500_000.0


def test_kiwoom_keeps_total_when_deposit_already_included():
    """총평가금액이 (보유합계+예수금)에 가까우면 이미 포함된 것 → 더하면 이중계상이다."""
    raw = {"summary": {"총평가금액": "1,500,000", "예수금": "500,000"},
           "holdings": [{"종목코드": "A005930", "종목명": "삼성전자", "평가금액": "1,000,000"}]}
    acct = ar.build_kiwoom_account(raw, prev_krw=None)
    assert acct["balance_krw"] == 1_500_000.0
    assert acct["securities_krw"] == 1_000_000.0


def test_kis_foreign_total_includes_deposit():
    """실계좌 검증(2026-07-29): 예수금이 총액의 14.8%였고 그만큼 빠져 있었다."""
    raw = {"securities_usd": 1000.0, "deposit_usd": 174.0, "usd_value": 1174.0,
           "eval_pnl_usd": -25.0, "principal_usd": 1025.0, "holdings": []}
    acct = ar.build_kis_foreign_account(raw, usdkrw=1400.0, prev_krw=None)
    assert acct["usd_value"] == 1174.0
    assert acct["securities_usd"] == 1000.0 and acct["deposit_usd"] == 174.0
    assert acct["securities_krw"] == 1_400_000.0 and acct["deposit_krw"] == 243_600.0
    assert acct["balance_krw"] == round(1174.0 * 1400.0, 2)


def test_kis_foreign_principal_excludes_deposit():
    """원가를 예수금 포함 총액에서 역산하면 손익률이 실제보다 작아진다 — 그걸 막는다."""
    raw = {"securities_usd": 1000.0, "deposit_usd": 174.0, "usd_value": 1174.0,
           "eval_pnl_usd": -25.0, "holdings": []}  # principal_usd 미보고 → 역산 경로
    acct = ar.build_kis_foreign_account(raw, usdkrw=1400.0, prev_krw=None)
    assert acct["principal_usd"] == 1025.0          # 1000 − (−25), 예수금 제외
    assert acct["eval_pnl_pct"] == round(-25.0 / 1025.0 * 100, 2)


def test_missing_deposit_does_not_fabricate_zero():
    """예수금을 못 받은 소스는 결측으로 남는다 — 0원으로 채우면 없는 사실을 만든다."""
    raw = {"securities_usd": 1000.0, "deposit_usd": None, "usd_value": 1000.0,
           "eval_pnl_usd": None, "holdings": []}
    acct = ar.build_kis_foreign_account(raw, usdkrw=1400.0, prev_krw=None)
    assert acct["deposit_usd"] is None and acct["deposit_krw"] is None


def test_collector_sum_helper_omits_when_all_missing():
    from collectors.kis_collector import _add

    assert _add(None, None) is None      # 결측 + 결측 = 결측(0 아님)
    assert _add(1000.0, None) == 1000.0  # 한쪽만 있으면 그 값
    assert _add(1000.0, 174.0) == 1174.0
