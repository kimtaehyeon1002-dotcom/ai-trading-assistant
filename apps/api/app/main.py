"""FastAPI 앱 팩토리. (설계서 §1.2)"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("startup", env=settings.app_env, claude_enabled=bool(settings.anthropic_api_key))
    try:
        from app.scheduler.scheduler import start_scheduler, shutdown_scheduler

        start_scheduler()
    except Exception as exc:  # noqa: BLE001 - 스케줄러 실패가 앱 기동을 막지 않음
        log.warning("scheduler_start_failed", error=str(exc))
        shutdown_scheduler = None  # type: ignore[assignment]
    yield
    if shutdown_scheduler is not None:
        shutdown_scheduler()
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Th_bot API",
        version="0.1.0",
        description="AI 투자 리서치/비서 — 판단 보조(매수/매도 추천 없음)",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
