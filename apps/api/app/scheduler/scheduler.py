"""APScheduler 인프로세스 스케줄러 — 평일 06:00 테마 / 06:30 모닝리포트(KST). 설계서 §1.5, §8.1.

Phase 7에서 Celery beat(단일+락)로 이관. SCHEDULER_ENABLED=false 면 비활성(테스트/워커 분리).
apscheduler는 lazy-import(미설치 환경에서 앱 임포트가 깨지지 않도록).
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("scheduler")

_scheduler: Any | None = None


def start_scheduler() -> Any | None:
    global _scheduler
    if not settings.scheduler_enabled:
        log.info("scheduler_disabled")
        return None
    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    from app.scheduler import jobs

    sched = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    if settings.morning_enabled:
        # 테마 스코어는 모닝리포트 30분 전 산출(같은 평일·시각 기준)
        theme_minute = max(0, settings.morning_minute - 30)
        sched.add_job(
            jobs.compute_theme_scores_job,
            CronTrigger(day_of_week="mon-fri", hour=settings.morning_hour, minute=theme_minute),
            id="theme_scores",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )
        # 모닝리포트: 평일(월~금) 지정 시각 1회만
        sched.add_job(
            jobs.generate_morning_report_job,
            CronTrigger(
                day_of_week="mon-fri", hour=settings.morning_hour, minute=settings.morning_minute
            ),
            id="morning_report",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )
    sched.start()
    _scheduler = sched
    log.info(
        "scheduler_started",
        tz=settings.scheduler_timezone,
        morning=f"{settings.morning_hour:02d}:{settings.morning_minute:02d} mon-fri"
        if settings.morning_enabled
        else "disabled",
    )
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler_stopped")
