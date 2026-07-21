"""자산 암호화 왕복 검증(design/20 Phase 8 DoD 2) — PBKDF2+AES-GCM.

브라우저 WebCrypto와의 상호운용성은 실측 확인 완료(2026-07-22, Claude_Browser 콘솔에서 이
모듈이 만든 envelope을 crypto.subtle로 직접 복호화해 원문과 일치함을 확인) — 파이썬 쪽
왕복은 여기서, 알고리즘 파라미터 일치는 static/js/asset-gate.js 주석에 실측 근거로 남긴다.
"""
from __future__ import annotations

import pytest

from utils.crypto import PBKDF2_ITERATIONS, decrypt, encrypt


def test_roundtrip_recovers_original_payload():
    payload = {"total_assets": 167504000, "accounts": {"kiwoom": 84120000}}
    envelope = encrypt(payload, "correct horse battery staple")
    assert decrypt(envelope, "correct horse battery staple") == payload


def test_wrong_passphrase_fails_to_decrypt():
    envelope = encrypt({"x": 1}, "right-pass")
    with pytest.raises(Exception):
        decrypt(envelope, "wrong-pass")


def test_envelope_uses_fresh_salt_and_iv_each_call():
    a = encrypt({"x": 1}, "same-pass")
    b = encrypt({"x": 1}, "same-pass")
    assert a["salt"] != b["salt"]
    assert a["iv"] != b["iv"]
    assert a["ciphertext"] != b["ciphertext"]


def test_envelope_records_owasp_iteration_count():
    envelope = encrypt({"x": 1}, "pass")
    assert envelope["iterations"] == PBKDF2_ITERATIONS
    assert PBKDF2_ITERATIONS >= 210_000


def test_envelope_has_no_plaintext_leak_in_json_keys():
    """직렬화된 envelope 자체에 평문 필드명이 없어야 한다(암호문 blob 하나뿐)."""
    envelope = encrypt({"total_assets": 999999999}, "pass")
    assert set(envelope.keys()) == {"salt", "iv", "iterations", "ciphertext"}
