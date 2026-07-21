"""KIS·BYBIT 수집기(design/20 Phase 8) — 미설정 시 결측 계약 + 서명 로직 순수 검증.

이 세션엔 실제 키가 없어 라이브 API 응답은 검증하지 못한다(collectors 모듈 docstring 참조) —
여기서는 (1) 키 미설정 시 정직하게 None을 반환하는지, (2) 네트워크 없이도 검증 가능한 순수
로직(HMAC 서명)이 스펙대로 동작하는지만 확인한다.
"""
from __future__ import annotations

import hashlib
import hmac

from collectors import bybit_collector, kis_collector


def test_kis_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(kis_collector, "KIS_APP_KEY", "")
    monkeypatch.setattr(kis_collector, "KIS_APP_SECRET", "")
    assert kis_collector.enabled() is False
    assert kis_collector.collect_overseas_balance() is None
    assert kis_collector.collect_isa_balance() is None


def test_bybit_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(bybit_collector, "BYBIT_API_KEY", "")
    monkeypatch.setattr(bybit_collector, "BYBIT_API_SECRET", "")
    assert bybit_collector.enabled() is False
    assert bybit_collector.collect_wallet_balance() is None


def test_bybit_sign_matches_hmac_sha256_spec(monkeypatch):
    """Bybit v5 서명 공식(timestamp+api_key+recv_window+queryString) 그대로 구현됐는지 순수 검증."""
    monkeypatch.setattr(bybit_collector, "BYBIT_API_KEY", "testkey")
    monkeypatch.setattr(bybit_collector, "BYBIT_API_SECRET", "testsecret")
    timestamp = "1700000000000"
    query = "accountType=UNIFIED"
    expected_payload = f"{timestamp}testkey5000{query}"
    expected = hmac.new(b"testsecret", expected_payload.encode(), hashlib.sha256).hexdigest()
    assert bybit_collector._sign(timestamp, query) == expected
