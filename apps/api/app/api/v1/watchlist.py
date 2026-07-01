"""워치리스트 라우터 (Phase 2~3 자리)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"], dependencies=[Depends(get_current_user)])
_NOT_YET = "Phase 3에서 구현 예정 (모닝리포트 관심종목)."


@router.get("")
async def get_watchlist() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_YET)
