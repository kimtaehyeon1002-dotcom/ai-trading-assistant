"""Celery 앱 — APScheduler 인프로세스 → Celery/Redis 다중 워커 이관 경로(Phase 7). 설계서 §1.4, §1.5.

worker 이미지의 엔트리에서만 임포트한다(앱 임포트 시 celery를 강제하지 않음). 큐 우선순위:
realtime_research > journal > batch_report. 멱등키·가시성 타임아웃·DLQ는 운영에서 설정.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("thbot", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.run_research_task": {"queue": "realtime_research"},
        "app.workers.tasks.analyze_journal_task": {"queue": "journal"},
        "app.workers.tasks.generate_morning_report_task": {"queue": "batch_report"},
    },
    # Celery beat로 전환 시 APScheduler 대체(단일 beat + 락)
    beat_schedule={
        "theme-scores-0600": {
            "task": "app.workers.tasks.compute_theme_scores_task",
            "schedule": crontab(hour=6, minute=0, day_of_week="mon-fri"),
        },
        "morning-report-0630": {
            "task": "app.workers.tasks.generate_morning_report_task",
            "schedule": crontab(hour=6, minute=30, day_of_week="mon-fri"),
        },
    },
    timezone=settings.scheduler_timezone,
)
