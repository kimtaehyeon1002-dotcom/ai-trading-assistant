"""뉴스 → RAG 인입 배치 스크립트(Phase 2.5).

제목+자체요약만 임베딩해 rag_chunk에 적재(본문 미저장, 저작권 안전). 스케줄러(뉴스 5~15분)
연동 전 수동 실행/cron용. VOYAGE_API_KEY 없으면 결정적 스텁 임베딩으로 동작.

사용: python -m scripts.ingest_news_rag [KR|US] [limit]
"""
from __future__ import annotations

import asyncio
import sys

from app.core.db import SessionLocal
from app.services import rag_service


async def main(market: str | None, limit: int) -> None:
    async with SessionLocal() as session:
        result = await rag_service.ingest_news(session, market=market, limit=limit)
    print(f"ingest_news_rag: {result}")


if __name__ == "__main__":
    mkt = sys.argv[1] if len(sys.argv) > 1 else None
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    asyncio.run(main(mkt, lim))
