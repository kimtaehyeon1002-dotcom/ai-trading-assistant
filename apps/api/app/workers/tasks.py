"""Celery 태스크 — 파이프라인을 워커에서 실행(Phase 7). 설계서 §1.4.

각 태스크는 자체 async 세션으로 파이프라인을 호출한다(앱 코드 재사용). 워커에서만 임포트.
"""
from __future__ import annotations

import asyncio

from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="app.workers.tasks.generate_morning_report_task")
def generate_morning_report_task() -> None:
    from app.agents.pipelines.morning_report import generate_morning_report
    from app.core.db import SessionLocal

    async def go():
        async with SessionLocal() as session:
            await generate_morning_report(session)

    _run(go())


@celery_app.task(name="app.workers.tasks.compute_theme_scores_task")
def compute_theme_scores_task() -> None:
    from app.analytics.theme_scoring import engine as theme_engine
    from app.core.db import SessionLocal

    async def go():
        async with SessionLocal() as session:
            for market in ("US", "KR"):
                for tf in ("intraday", "swing", "long"):
                    await theme_engine.compute_theme_scores(session, market=market, timeframe=tf)

    _run(go())
