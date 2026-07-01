"""SSE 스트리밍 유틸. Phase 2 리서치 스트리밍이 재사용.

이벤트 타입 규약: token | stage | tool | done | error
고위험 컴플라이언스 카테고리는 '지연 스트리밍'(문장 단위 버퍼→검증→방출)을
Phase 2 가드레일에서 적용한다(설계서 §2.6).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any


def sse_event(event: str, data: Any, *, event_id: str | None = None) -> str:
    """단일 SSE 메시지 직렬화."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


async def keepalive_comment() -> str:
    return ": keep-alive\n\n"


SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def passthrough(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    async for chunk in stream:
        yield chunk
