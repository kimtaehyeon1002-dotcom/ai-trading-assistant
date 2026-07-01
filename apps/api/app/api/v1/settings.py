"""사용자 설정 라우터 — 투자 스타일/시장/알림 선호."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(user: User = Depends(get_current_user)) -> dict:
    return {
        "investment_styles": user.investment_styles,
        "locale": user.locale,
        "timezone": user.timezone,
        "plan": user.plan,
        # 모닝리포트 기준값(평일 지정시각 1회) — .env로 설정
        "morning_report": {
            "enabled": settings.morning_enabled,
            "send_time": f"{settings.morning_hour:02d}:{settings.morning_minute:02d}",
            "days": "Mon-Fri",
            "timezone": settings.scheduler_timezone,
            "markets": settings.morning_markets_list,
            "style": settings.morning_style,
            "top_themes": settings.morning_top_themes,
            "min_theme_score": settings.morning_min_theme_score,
            "model": "opus" if settings.morning_use_opus else "sonnet",
        },
        # 비용 절감 설정
        "cost_savers": {
            "prompt_cache": settings.llm_prompt_cache,
            "research_cache_same_day": settings.research_cache_same_day,
            "rag_top_k": settings.rag_top_k,
        },
    }
