"""사용량/요금제 라우터 — 일일 LLM 비용·잔여 한도 조회. 설계서 §1.6, §8.1."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.user import User
from app.services import usage_service

router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[Depends(get_current_user)])


@router.get("")
async def get_usage(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    return await usage_service.get_usage(session, user.user_id)
