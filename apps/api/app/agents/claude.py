"""Claude API 래퍼 — 모델 라우팅 + 비용 계산 + agent_run 적재.

- ANTHROPIC_API_KEY가 없으면 '스텁 모드'로 동작(네트워크 없이 구조/로깅 검증 가능).
- 프롬프트 캐싱(read ~0.1x, write 1.25x) 비용을 반영.
- Phase 2 리서치/모닝리포트 파이프라인이 이 래퍼를 그대로 호출한다.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.router import PRICING, Task, model_for
from app.core.config import settings
from app.core.logging import get_logger
from app.models.agent_run import AgentRun

log = get_logger("claude")


@dataclass
class ClaudeResult:
    text: str
    model: str
    task_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0
    is_stub: bool = False
    raw: dict | None = field(default=None, repr=False)

    @property
    def cost_usd(self) -> float:
        price_in, price_out = PRICING.get(self.model, (3.0, 15.0))
        return round(
            (
                self.input_tokens * price_in
                + self.output_tokens * price_out
                + self.cache_read_tokens * price_in * 0.1
                + self.cache_write_tokens * price_in * 1.25
            )
            / 1_000_000,
            6,
        )


class ClaudeClient:
    def __init__(self) -> None:
        self._client = None
        if settings.anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            except Exception as exc:  # noqa: BLE001
                log.warning("claude_init_failed", error=str(exc))

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def complete(
        self,
        task: Task | str,
        *,
        system: str | None = None,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
        adaptive_thinking: bool = False,
    ) -> ClaudeResult:
        task_str = task.value if isinstance(task, Task) else str(task)
        chosen = model or model_for(task)
        started = time.perf_counter()

        if not self.enabled:
            # 스텁: 네트워크 없이도 파이프라인/로깅 검증
            return ClaudeResult(
                text="[stub] ANTHROPIC_API_KEY 미설정 — 오프라인 스텁 응답",
                model=chosen,
                task_type=task_str,
                latency_ms=int((time.perf_counter() - started) * 1000),
                is_stub=True,
            )

        kwargs: dict = {"model": chosen, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = _system_param(system)
        if adaptive_thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        resp = await self._client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        usage = resp.usage
        return ClaudeResult(
            text=text,
            model=chosen,
            task_type=task_str,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def stream(
        self,
        task: Task | str,
        *,
        system: str | None = None,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 2048,
        stub_text: str | None = None,
    ) -> AsyncIterator[dict]:
        """텍스트 델타를 순차 yield 후, 마지막에 {'type':'final','result':ClaudeResult}.

        스텁 모드(API 키 없음)에서는 stub_text를 청크로 흘려보낸다 → 파이프라인/SSE 검증 가능.
        Phase 2 리서치 합성이 문장 게이트(streaming_gate)와 함께 사용한다.
        """
        task_str = task.value if isinstance(task, Task) else str(task)
        chosen = model or model_for(task)
        started = time.perf_counter()

        if not self.enabled:
            text = stub_text or "[stub] 오프라인 스텁 스트림."
            for chunk in _chunk_text(text):
                yield {"type": "text", "text": chunk}
            yield {
                "type": "final",
                "result": ClaudeResult(
                    text=text,
                    model=chosen,
                    task_type=task_str,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    is_stub=True,
                ),
            }
            return

        kwargs: dict = {"model": chosen, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = _system_param(system)
        acc: list[str] = []
        async with self._client.messages.stream(**kwargs) as s:
            async for delta in s.text_stream:
                acc.append(delta)
                yield {"type": "text", "text": delta}
            final = await s.get_final_message()
        usage = final.usage
        yield {
            "type": "final",
            "result": ClaudeResult(
                text="".join(acc),
                model=chosen,
                task_type=task_str,
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                latency_ms=int((time.perf_counter() - started) * 1000),
            ),
        }


def _chunk_text(text: str, size: int = 24) -> list[str]:
    """스텁 스트림용 — 텍스트를 size 글자 단위 청크로."""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _system_param(system: str):
    """시스템 프롬프트 — 캐싱 켜지면 ephemeral cache_control 블록으로 전달(입력비 0.1x).

    가드레일+역할 프리픽스는 호출마다 동일하므로 캐시 적중률이 높다(타임스탬프/UUID 미삽입).
    프리픽스가 모델 최소 캐시 토큰 미만이면 API가 무시(무해).
    """
    if not settings.llm_prompt_cache:
        return system
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


async def persist_agent_run(
    session: AsyncSession,
    result: ClaudeResult,
    *,
    user_id: uuid.UUID | None = None,
    status: str = "ok",
    is_batch: bool = False,
    prompt_version: str | None = None,
) -> AgentRun:
    """ClaudeResult를 agent_run에 적재(비용 대시보드 백본)."""
    run = AgentRun(
        user_id=user_id,
        task_type=result.task_type,
        model=result.model,
        prompt_version=prompt_version,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        is_batch=is_batch,
        status="stub" if result.is_stub else status,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


_claude: ClaudeClient | None = None


def get_claude() -> ClaudeClient:
    global _claude
    if _claude is None:
        _claude = ClaudeClient()
    return _claude
