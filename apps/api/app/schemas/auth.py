"""인증 요청/응답 스키마."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access 토큰 만료(초)


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    investment_styles: list[str]
