"""API v1 라우터 집합."""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    health,
    journal,
    market,
    portfolio,
    reports,
    research,
    settings,
    system,
    usage,
    watchlist,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(system.router)
api_router.include_router(research.router)
api_router.include_router(reports.router)
api_router.include_router(usage.router)
api_router.include_router(journal.router)
api_router.include_router(portfolio.router)
api_router.include_router(watchlist.router)
api_router.include_router(settings.router)
