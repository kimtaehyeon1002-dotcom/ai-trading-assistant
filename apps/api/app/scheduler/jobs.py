"""스케줄 잡 본문 — 테마 스코어(06:00) / 모닝리포트(06:30). 설계서 §1.3-A, §2.7.

각 잡은 자체 DB 세션을 열고 예외를 격리한다(한 시장/스타일 실패가 전체를 막지 않음).
"""
from __future__ import annotations

from app.agents.pipelines.morning_report import generate_morning_report
from app.analytics.theme_scoring import engine as theme_engine
from app.core.db import SessionLocal
from app.core.logging import get_logger

log = get_logger("scheduler_jobs")


async def compute_theme_scores_job() -> None:
    async with SessionLocal() as session:
        for market in ("US", "KR"):
            for tf in ("intraday", "swing", "long"):
                try:
                    await theme_engine.compute_theme_scores(session, market=market, timeframe=tf)
                except Exception as exc:  # noqa: BLE001 - 잡 격리
                    log.warning("theme_scores_job_failed", market=market, tf=tf, error=str(exc))


async def generate_morning_report_job() -> None:
    async with SessionLocal() as session:
        try:
            await generate_morning_report(session)
        except Exception as exc:  # noqa: BLE001 - 잡 격리
            log.warning("morning_report_job_failed", error=str(exc))
