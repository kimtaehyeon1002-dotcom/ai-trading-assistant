"""키움 예수금 수집 — 잔고(opw00018)와 별개 TR(opw00001)을 호출하는지 검증.

배경(2026-08-03): 키움만 예수금이 계속 결측이었다. opw00018에 "예수금" 필드 후보를 걸어
뒀지만 그 TR은 유가증권 평가 계열만 돌려준다 — 예수금은 opw00001 소관이다.

실제 OCX는 32비트 Windows + HTS 로그인이 필요해 여기서 돌릴 수 없으므로, comm_rq를 가짜로
바꿔 **호출 순서·필드 병합 규칙**만 검증한다. 응답 필드명 자체가 맞는지는 데스크톱 실행의
'예수금 raw(필드 진단용)' 로그로 확인해야 한다.
"""
from __future__ import annotations

from collectors.kiwoom_desktop import account as acct


class _FakeAPI:
    """comm_rq 호출을 기록하고 TR별로 미리 정한 응답을 돌려주는 스텁."""

    def __init__(self, responses):
        self._responses = responses
        self.calls = []
        self.inputs = []

    def set_input(self, key, value):
        self.inputs.append((key, value))

    def comm_rq(self, rq_name, tr_code, **kwargs):
        self.calls.append(tr_code)
        return self._responses.get(tr_code, {"rows": []})


_BALANCE_ROWS = {"rows": [{
    "종목번호": "A005930", "종목명": "삼성전자", "보유수량": "10",
    "매입가": "70000", "현재가": "80000", "평가금액": "800000",
    "평가손익": "100000", "수익률(%)": "14.28",
    "총평가금액": "800000", "총매입금액": "700000", "총평가손익금액": "100000",
    # opw00018에는 예수금이 없다 — 실제 응답을 그대로 재현
}]}

_DEPOSIT_ROWS = {"rows": [{"예수금": "1,234,567", "주문가능금액": "1,200,000"}]}


def test_deposit_is_fetched_from_separate_tr():
    """★핵심: 잔고 TR에 예수금이 없으면 opw00001을 추가 호출해 채운다."""
    api = _FakeAPI({acct._BALANCE_TR_CODE: _BALANCE_ROWS, acct._DEPOSIT_TR_CODE: _DEPOSIT_ROWS})
    result = acct.fetch_balance(api, "1234567890")

    assert api.calls == [acct._BALANCE_TR_CODE, acct._DEPOSIT_TR_CODE]
    assert result["summary"]["예수금"] == "1,234,567"
    assert result["summary"]["주문가능금액"] == "1,200,000"


def test_balance_tr_value_wins_when_present():
    """잔고 TR이 예수금을 주는 환경이면 추가 호출 결과로 덮지 않는다."""
    balance = {"rows": [dict(_BALANCE_ROWS["rows"][0], 예수금="999", 주문가능금액="888")]}
    api = _FakeAPI({acct._BALANCE_TR_CODE: balance, acct._DEPOSIT_TR_CODE: _DEPOSIT_ROWS})
    result = acct.fetch_balance(api, "1234567890")

    assert acct._DEPOSIT_TR_CODE not in api.calls, "이미 값이 있으면 두 번째 TR을 부르지 않는다"
    assert result["summary"]["예수금"] == "999"


def test_deposit_failure_does_not_break_balance():
    """예수금 TR이 실패해도 잔고·보유종목은 그대로 반환된다(결측 문법)."""
    class _FailingDeposit(_FakeAPI):
        def comm_rq(self, rq_name, tr_code, **kwargs):
            self.calls.append(tr_code)
            if tr_code == acct._DEPOSIT_TR_CODE:
                raise RuntimeError("TR 조회 제한")
            return self._responses.get(tr_code, {"rows": []})

    api = _FailingDeposit({acct._BALANCE_TR_CODE: _BALANCE_ROWS})
    result = acct.fetch_balance(api, "1234567890")

    assert result is not None
    assert result["summary"]["총평가금액"] == "800000"
    assert result["summary"]["예수금"] == ""       # 결측이지 0이 아니다
    assert len(result["holdings"]) == 1


def test_deposit_tr_sends_required_inputs():
    """opw00001도 계좌번호·비밀번호입력매체구분·조회구분을 요구한다(누락 시 [400721] 계열 오류)."""
    api = _FakeAPI({acct._DEPOSIT_TR_CODE: _DEPOSIT_ROWS})
    acct.fetch_deposit(api, "1234567890")
    keys = [k for k, _ in api.inputs]
    assert {"계좌번호", "비밀번호", "비밀번호입력매체구분", "조회구분"} <= set(keys)
