"""인증 라우터 — 로그인/리프레시/로그아웃/me."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_ttl_min * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    return _tokens(str(user.user_id))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token"
        ) from exc
    return _tokens(payload["sub"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    # 무상태 JWT — 운영 단계에서 리프레시 토큰 폐기목록(Redis)으로 회전/폐기.
    return None


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        investment_styles=user.investment_styles,
    )
