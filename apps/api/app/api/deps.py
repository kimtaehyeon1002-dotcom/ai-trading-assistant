"""공통 FastAPI 의존성: DB 세션 + 현재 사용자(JWT)."""
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import decode_token
from app.models.user import User
from app.services import auth_service

bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_token(creds.credentials, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc
    user = await auth_service.get_user(session, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


async def get_current_user_sse(
    token: str = Query(..., description="EventSource는 헤더 설정 불가 → 쿼리로 access token 전달"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """SSE 전용 인증 — 토큰을 쿼리스트링으로 받는다(lib/sse-client.ts 규약)."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token"
        ) from exc
    user = await auth_service.get_user(session, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user
