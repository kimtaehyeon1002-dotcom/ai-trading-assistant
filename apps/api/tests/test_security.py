import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    tok = create_access_token("user-abc")
    payload = decode_token(tok, expected_type="access")
    assert payload["sub"] == "user-abc"
    assert payload["type"] == "access"


def test_token_type_mismatch_raises():
    refresh = create_refresh_token("user-abc")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(refresh, expected_type="access")
