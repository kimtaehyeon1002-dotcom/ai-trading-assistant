"""AI Research 잡 관리 — 인메모리 잡 레지스트리 + SSE 이벤트 큐 + 백그라운드 실행.

Phase 2는 단일 프로세스(인프로세스 스케줄러)이므로 잡 상태는 인메모리(asyncio).
수평 확장(Phase 7)에서는 Redis pub/sub로 이관한다(설계서 §1.4). 결과는 research_report에
영속화되어 result_url로 재조회 가능(프로세스 재시작에도 보존).
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.agents.pipelines.research import run_research_pipeline
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.schemas.research import ResearchRequest, ResearchResult

log = get_logger("research_job")

_DONE = object()  # 큐 종료 센티넬


@dataclass
class Job:
    job_id: str
    user_id: uuid.UUID
    request: ResearchRequest
    status: str = "pending"  # pending|running|completed|blocked|error
    error: str | None = None
    result: ResearchResult | None = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, user_id: uuid.UUID, request: ResearchRequest) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(job_id=job_id, user_id=user_id, request=request)
        self._jobs[job_id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def _run(self, job: Job) -> None:
        job.status = "running"

        async def push(event: str, data: object) -> None:
            await job.queue.put((event, data))

        async with SessionLocal() as session:
            try:
                result = await run_research_pipeline(
                    session, job.user_id, job.job_id, job.request, push
                )
                job.result = result
                job.status = result.status
            except Exception as exc:  # noqa: BLE001 - 잡 단위 격리
                job.status = "error"
                job.error = str(exc)
                log.warning("research_pipeline_error", job_id=job.job_id, error=str(exc))
                await job.queue.put(("error", {"message": "리서치 처리 중 오류가 발생했습니다."}))
            finally:
                await job.queue.put(_DONE)

    async def events(self, job: Job):
        """SSE용 (event, data) 튜플 제너레이터. _DONE 수신 시 종료."""
        while True:
            item = await job.queue.get()
            if item is _DONE:
                return
            yield item


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
