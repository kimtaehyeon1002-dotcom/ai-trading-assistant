"""인증 보안: 비밀번호 해시 + JWT 발급/검증."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# bcrypt를 직접 사용(passlib는 2020년 이후 미유지보수 + bcrypt 4.1+와 비호환).
# bcrypt는 72바이트 초과 비밀번호를 잘라내야 하므로 명시적으로 절단.
_BCRYPT_MAX = 72


def hash_password(raw: str) -> str:
    pw = raw.encode("utf-8")[:_BCRYPT_MAX]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8")[:_BCRYPT_MAX], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _encode(claims: dict[str, Any], ttl: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _encode({"sub": subject}, timedelta(minutes=settings.access_token_ttl_min), "access")


def create_refresh_token(subject: str) -> str:
    return _encode({"sub": subject}, timedelta(days=settings.refresh_token_ttl_days), "refresh")


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """검증 + 디코드. 실패 시 jwt 예외 전파(상위에서 401 매핑)."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload
