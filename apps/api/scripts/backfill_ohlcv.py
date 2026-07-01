"""시계열 백필 스크립트 (Phase 2~3 자리).

Provider 추상화로 일/분봉을 수집해 price_bar에 적재. price_bar 모델/파티셔닝은
Phase 2에서 추가(설계서 §4.1). 지금은 골격만.
"""
from __future__ import annotations

import asyncio


async def backfill() -> None:  # pragma: no cover - 골격
    raise NotImplementedError("Phase 2에서 price_bar 적재와 함께 구현")


if __name__ == "__main__":
    asyncio.run(backfill())
