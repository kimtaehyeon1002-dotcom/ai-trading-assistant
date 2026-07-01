"""헬스체크 — /healthz(라이브니스), /readyz(DB/Redis 준비)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis import get_redis

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/readyz")
async def readyz(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = f"error: {exc}"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"

    ready = all(v == "ok" for v in checks.values())
    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": ready, "checks": checks}
