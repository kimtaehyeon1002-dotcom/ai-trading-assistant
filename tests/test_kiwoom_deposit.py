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
    """★핵심: 잔고 TR에 예수금이 없으면 opw00001을 추가 호출해 채운다.

    채택값은 당일 예수금(1,234,567)이 아니라 결제 반영분(주문가능 1,200,000)이다 —
    당일 예수금은 T+2 미결제 매수대금을 아직 품고 있어 총자산을 부풀린다."""
    api = _FakeAPI({acct._BALANCE_TR_CODE: _BALANCE_ROWS, acct._DEPOSIT_TR_CODE: _DEPOSIT_ROWS})
    result = acct.fetch_balance(api, "1234567890")

    assert api.calls == [acct._BALANCE_TR_CODE, acct._DEPOSIT_TR_CODE]
    assert result["summary"]["예수금"] == "1,200,000"
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


class _ModeAPI:
    """조회구분 값별로 다른 응답을 주는 스텁 — 추정조회(3)/일반조회(2) 분기 검증용."""

    def __init__(self, by_mode):
        self.by_mode = by_mode
        self.mode = None
        self.modes = []

    def set_input(self, key, value):
        if key == "조회구분":
            self.mode = value

    def comm_rq(self, rq_name, tr_code, **kwargs):
        self.modes.append(self.mode)
        return {"rows": [self.by_mode.get(self.mode, {})]}


def test_d2_deposit_is_preferred_over_same_day():
    """★핵심: 당일 예수금을 쓰면 총자산이 부풀려진다(T+2 미결제 매수대금 이중계산).

    오늘 100만원어치를 사면 그 종목은 총평가금액에 이미 잡히는데 매수대금은 당일 예수금에
    아직 남아 있다. 계좌 총액 = 유가증권 + 예수금이므로 매수대금이 두 번 세어진다.
    D+2 추정예수금은 미결제분이 차감돼 있어 이 중복이 없다."""
    api = _ModeAPI({"3": {"d+2추정예수금": "156115", "예수금": "1156115",
                          "주문가능금액": "156115"}})
    out = acct.fetch_deposit(api, "1234567890")

    assert api.modes == ["3"], "추정조회를 먼저 호출해야 D+2 필드가 채워진다"
    assert out["예수금"] == "156115", "당일 예수금(1156115)이 아니라 D+2를 채택해야 한다"


def test_falls_back_to_normal_query_when_estimate_empty():
    """추정조회가 값을 못 주면 일반조회로 되돌아간다 — 예수금을 통째로 잃는 것보다 낫다."""
    api = _ModeAPI({"3": {}, "2": {"예수금": "156115", "주문가능금액": "156115"}})
    out = acct.fetch_deposit(api, "1234567890")

    assert api.modes == ["3", "2"]
    assert out["예수금"] == "156115"


def test_returns_empty_when_both_queries_have_nothing():
    api = _ModeAPI({"3": {}, "2": {}})
    assert acct.fetch_deposit(api, "1234567890")["예수금"] == ""


def test_deposit_tr_sends_required_inputs():
    """opw00001도 계좌번호·비밀번호입력매체구분·조회구분을 요구한다(누락 시 [400721] 계열 오류)."""
    api = _FakeAPI({acct._DEPOSIT_TR_CODE: _DEPOSIT_ROWS})
    acct.fetch_deposit(api, "1234567890")
    keys = [k for k, _ in api.inputs]
    assert {"계좌번호", "비밀번호", "비밀번호입력매체구분", "조회구분"} <= set(keys)
