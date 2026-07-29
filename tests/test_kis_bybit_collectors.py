"""KIS·BYBIT 수집기(design/20 Phase 8) — 미설정 시 결측 계약 + 서명 로직 순수 검증.

이 세션엔 실제 키가 없어 라이브 API 응답은 검증하지 못한다(collectors 모듈 docstring 참조) —
여기서는 (1) 키 미설정 시 정직하게 None을 반환하는지, (2) 네트워크 없이도 검증 가능한 순수
로직(HMAC 서명)이 스펙대로 동작하는지만 확인한다.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from collectors import bybit_collector, kis_collector


def test_kis_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(kis_collector, "KIS_APP_KEY", "")
    monkeypatch.setattr(kis_collector, "KIS_APP_SECRET", "")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_KEY", "")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_SECRET", "")
    assert kis_collector.enabled() is False
    assert kis_collector.collect_overseas_balance() is None
    assert kis_collector.collect_isa_balance() is None


def test_isa_uses_dedicated_credentials_when_present(monkeypatch):
    """★실측 근거: KIS 앱키는 발급 시 연결한 계좌에만 유효하다 — 위탁 앱키로 ISA를 조회하면
    상품코드를 무엇으로 바꿔도 INVALID_CHECK_ACNO. 계좌별 앱키가 실제로 분리되는지 확인한다."""
    monkeypatch.setattr(kis_collector, "KIS_APP_KEY", "foreign-key")
    monkeypatch.setattr(kis_collector, "KIS_APP_SECRET", "foreign-secret")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_KEY", "isa-key")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_SECRET", "isa-secret")
    assert kis_collector._foreign_credentials() == ("foreign-key", "foreign-secret")
    assert kis_collector._isa_credentials() == ("isa-key", "isa-secret")


def test_isa_falls_back_to_shared_credentials(monkeypatch):
    """ISA 전용 키가 없으면 공용 키로 폴백 — 두 계좌가 한 앱키에 묶인 사용자 하위 호환."""
    monkeypatch.setattr(kis_collector, "KIS_APP_KEY", "shared-key")
    monkeypatch.setattr(kis_collector, "KIS_APP_SECRET", "shared-secret")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_KEY", "")
    monkeypatch.setattr(kis_collector, "KIS_ISA_APP_SECRET", "")
    assert kis_collector._isa_credentials() == ("shared-key", "shared-secret")


def test_token_cache_is_per_app_key(monkeypatch):
    """★회귀: 토큰 캐시가 전역 1개면 먼저 조회한 계좌의 토큰을 다른 계좌가 물려받아,
    그 계좌에 유효하지 않은 토큰으로 요청하게 된다(증상이 '계좌번호 오류'로 나타나 추적이 어렵다)."""
    issued = []

    class _FakeTokenResp:
        def __init__(self, token):
            self._token = token

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": self._token, "expires_in": 86400}

    def fake_post(url, json=None, timeout=None):
        issued.append(json["appkey"])
        return _FakeTokenResp("token-for-" + json["appkey"])

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(kis_collector, "_memo_tokens", {})

    assert kis_collector._get_token("key-a", "secret-a") == "token-for-key-a"
    assert kis_collector._get_token("key-b", "secret-b") == "token-for-key-b"
    # 같은 앱키 재요청은 캐시 적중(발급 1분당 1회 제한이라 재사용이 필수)
    assert kis_collector._get_token("key-a", "secret-a") == "token-for-key-a"
    assert issued == ["key-a", "key-b"]


def test_bybit_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(bybit_collector, "BYBIT_API_KEY", "")
    monkeypatch.setattr(bybit_collector, "BYBIT_API_SECRET", "")
    assert bybit_collector.enabled() is False
    assert bybit_collector.collect_wallet_balance() is None


def test_split_account_strips_hyphen_before_slicing():
    """★회귀: HTS는 계좌번호를 '12345678-01'처럼 하이픈 포함으로 표시한다 — naive
    acct[:8]/acct[8:10] 슬라이싱은 하이픈이 상품코드 자리를 차지해 조회 자체가 깨진다
    (실키 연동 검증 중 실제로 재현됨: ACNT_PRDT_CD가 '-0'이 되어 API가 토큰 오류로 응답)."""
    assert kis_collector._split_account("12345678-01") == ("12345678", "01")
    assert kis_collector._split_account("1234567801") == ("12345678", "01")
    assert kis_collector._split_account("12345678") == ("12345678", "")


def test_first_row_accepts_dict_or_list_or_none():
    """★회귀: 위탁(해외) 잔고 output2는 실키로 확인 결과 dict로 온다(리스트 아님) —

    원래 코드는 `(output2 or [{}])[0]`로 리스트를 전제해서, dict가 오면 `dict[0]`이
    KeyError(0)을 던지며 조용히 실패했다(예외 str이 '0'이라 원인 파악도 어려웠다)."""
    assert kis_collector._first_row({"a": 1}) == {"a": 1}
    assert kis_collector._first_row([{"a": 1}, {"a": 2}]) == {"a": 1}
    assert kis_collector._first_row([]) == {}
    assert kis_collector._first_row(None) == {}


def test_sum_field_totals_across_rows_when_summary_lacks_total():
    """★회귀: 위탁(해외) 잔고의 output2에는 총평가금액 필드 자체가 없다(실키로 확인) —

    종목별 evlu_amt 합산으로 대체해야 한다."""
    rows = [{"ovrs_stck_evlu_amt": "100.50"}, {"ovrs_stck_evlu_amt": "200.25"}]
    assert kis_collector._sum_field(rows, "ovrs_stck_evlu_amt") == 300.75


def test_sum_field_none_when_no_row_has_the_field():
    assert kis_collector._sum_field([{"other": "1"}], "ovrs_stck_evlu_amt") is None


def test_collect_overseas_balance_derives_usd_value_from_holdings(monkeypatch):
    """실제 응답 형태(output2=dict, 총액 필드 없음)를 재현해 usd_value가 종목 합산으로 채워지는지 확인."""
    monkeypatch.setattr(kis_collector, "KIS_APP_KEY", "k")
    monkeypatch.setattr(kis_collector, "KIS_APP_SECRET", "s")
    monkeypatch.setattr(kis_collector, "KIS_ACCOUNT_FOREIGN", "12345678-01")
    monkeypatch.setattr(kis_collector, "_get_token", lambda *_: "tok")

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "rt_cd": "0",
                "output1": [
                    {"ovrs_item_name": "APPLE INC", "ovrs_pdno": "AAPL", "ovrs_cblc_qty": "10",
                     "pchs_avg_pric": "150.00", "now_pric2": "160.00", "ovrs_stck_evlu_amt": "1600.00",
                     "frcr_evlu_pfls_amt": "100.00", "evlu_pfls_rt": "6.67"},
                ],
                # 실측 그대로 재현 — 총평가금액 필드 없이 손익 계열만 있는 dict(리스트 아님)
                "output2": {"frcr_pchs_amt1": "1500.00", "ovrs_tot_pfls": "100.00"},
            }

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResp())

    result = kis_collector.collect_overseas_balance()
    assert result is not None
    assert result["usd_value"] == 1600.00  # summary엔 없으니 holdings 합산
    assert result["eval_pnl_usd"] == 100.00
    assert result["principal_usd"] == 1500.00


def test_kis_pick_float_walks_candidate_field_names():
    """KIS 응답 필드명이 미검증이라 후보를 순서대로 시도한다 — 첫 유효값 채택, 없으면 결측."""
    row = {"pchs_amt_smtl": "", "pchs_amt_smtl_amt": "74,780,000"}
    assert kis_collector._pick_float(row, "pchs_amt_smtl", "pchs_amt_smtl_amt") == 74_780_000.0
    assert kis_collector._pick_float(row, "nope", "nada") is None


def test_bybit_timestamp_is_corrected_by_server_offset(monkeypatch):
    """★회귀: Bybit은 타임스탬프가 서버보다 **미래이면 recv_window와 무관하게 거부**한다.

    실제 사고 — 로컬 시계가 서버보다 ~1초 빨라서 매 실행 결측이었고, 로그는
    'invalid request, please check your server timestamp or recv_window param'였다.
    서버 시각으로 보정하고 안전 여유만큼 과거로 치우치는지 확인한다."""
    monkeypatch.setattr(bybit_collector, "_clock_offset_ms", None)

    class _TimeResp:
        def raise_for_status(self):
            pass

        def json(self):
            # 서버가 로컬보다 2초 느린 상황(로컬이 2초 빠름 = 거부되던 조건)
            return {"result": {"timeNano": str((int(time.time() * 1000) - 2000) * 1_000_000)}}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _TimeResp())

    offset = bybit_collector._server_offset_ms()
    assert offset < -1500, "로컬이 빠른 상황이 음수 오프셋으로 측정돼야 한다"

    ts = int(bybit_collector._timestamp_ms())
    local_now = int(time.time() * 1000)
    assert ts < local_now, "보정된 타임스탬프는 로컬 시계보다 과거여야 한다(미래는 즉시 거부)"


def test_bybit_offset_falls_back_to_zero_when_server_time_unavailable(monkeypatch):
    """서버 시각 조회가 실패해도 수집 자체를 막지 않는다(로컬 시계로 폴백)."""
    monkeypatch.setattr(bybit_collector, "_clock_offset_ms", None)

    def _boom(*a, **k):
        raise OSError("network down")

    import requests
    monkeypatch.setattr(requests, "get", _boom)
    assert bybit_collector._server_offset_ms() == 0


def test_bybit_sign_matches_hmac_sha256_spec(monkeypatch):
    """Bybit v5 서명 공식(timestamp+api_key+recv_window+queryString) 그대로 구현됐는지 순수 검증."""
    monkeypatch.setattr(bybit_collector, "BYBIT_API_KEY", "testkey")
    monkeypatch.setattr(bybit_collector, "BYBIT_API_SECRET", "testsecret")
    timestamp = "1700000000000"
    query = "accountType=UNIFIED"
    expected_payload = f"{timestamp}testkey5000{query}"
    expected = hmac.new(b"testsecret", expected_payload.encode(), hashlib.sha256).hexdigest()
    assert bybit_collector._sign(timestamp, query) == expected
