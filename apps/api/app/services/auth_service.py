"""인증 도메인 서비스 — 로컬 비밀번호 검증 + 사용자 조회/생성."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import AuthCredential, User


def _norm_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == _norm_email(email)))
    return res.scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if user is None or user.status != "active":
        return None
    res = await session.execute(
        select(AuthCredential).where(
            AuthCredential.user_id == user.user_id, AuthCredential.provider == "local"
        )
    )
    cred = res.scalar_one_or_none()
    if cred is None or not cred.password_hash:
        return None
    if not verify_password(password, cred.password_hash):
        return None
    return user


async def create_local_user(
    session: AsyncSession,
    email: str,
    password: str,
    *,
    display_name: str | None = None,
    role: str = "OWNER",
    investment_styles: list[str] | None = None,
) -> User:
    email = _norm_email(email)
    user = User(
        email=email,
        display_name=display_name,
        role=role,
        investment_styles=investment_styles or ["swing"],
    )
    session.add(user)
    await session.flush()  # user_id 확보
    session.add(
        AuthCredential(
            user_id=user.user_id,
            provider="local",
            provider_subject=email,
            password_hash=hash_password(password),
        )
    )
    await session.commit()
    await session.refresh(user)
    return user
