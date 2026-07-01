"""pgvector 저장/검색 — rag_document 적재(중복 제거) + rag_chunk 벡터 ANN. 설계서 §5.2.

검색은 코사인 거리 ANN + 메타/권한 필터. ef_search를 트랜잭션 로컬로 설정(풀 오염 방지).
하이브리드(BM25+RRF)·rerank·시간가중은 Phase 6에서 retrieve.py로 확장.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.chunking import Chunk
from app.models.rag import RagChunk, RagDocument


async def get_document_by_hash(session: AsyncSession, content_hash: str) -> RagDocument | None:
    res = await session.execute(
        select(RagDocument).where(RagDocument.content_hash == content_hash)
    )
    return res.scalars().first()


async def add_document_with_chunks(
    session: AsyncSession,
    *,
    source_table: str,
    source_pk: str,
    doc_type: str,
    title: str | None,
    url: str | None,
    language: str,
    market: str | None,
    published_at: datetime | None,
    content_hash: str,
    instrument_id: int | None,
    symbols: list[str],
    chunks: list[Chunk],
    embeddings: list[list[float]],
    embed_model: str,
    owner_user_id: uuid.UUID | None = None,
    is_public: bool = True,
    license_ok: bool = True,
) -> RagDocument:
    doc = RagDocument(
        source_table=source_table,
        source_pk=source_pk,
        doc_type=doc_type,
        title=title,
        url=url,
        language=language,
        market=market,
        published_at=published_at,
        content_hash=content_hash,
        instrument_id=instrument_id,
        owner_user_id=owner_user_id,
        is_public=is_public,
        license_ok=license_ok,
    )
    session.add(doc)
    await session.flush()  # doc_id 확보

    for ch, emb in zip(chunks, embeddings, strict=True):
        session.add(
            RagChunk(
                doc_id=doc.doc_id,
                chunk_index=ch.index,
                content=ch.content,
                embedding=emb,
                embed_model=embed_model,
                content_tsv=func.to_tsvector("simple", ch.content),
                symbols=symbols,
                doc_type=doc_type,
                language=language,
                market=market,
                published_at=published_at,
                owner_user_id=owner_user_id,
                is_public=is_public,
                license_ok=license_ok,
            )
        )
    await session.commit()
    await session.refresh(doc)
    return doc


def _apply_filters(
    stmt,
    *,
    symbols: list[str] | None,
    market: str | None,
    doc_types: list[str] | None,
    since: datetime | None,
    user_id: uuid.UUID | None,
):
    """권한(공개 OR 본인) + 메타 필터. 개인 노트 격리(owner_user_id)도 여기서. 설계서 §6 RLS."""
    stmt = stmt.where(RagChunk.license_ok.is_(True)).where(
        or_(RagChunk.is_public.is_(True), RagChunk.owner_user_id == user_id)
    )
    if symbols:
        stmt = stmt.where(RagChunk.symbols.overlap(symbols))
    if market:
        stmt = stmt.where(RagChunk.market == market)
    if doc_types:
        stmt = stmt.where(RagChunk.doc_type.in_(doc_types))
    if since:
        stmt = stmt.where(RagChunk.published_at >= since)
    return stmt


async def vector_search(
    session: AsyncSession,
    qvec: list[float],
    *,
    k: int = 8,
    symbols: list[str] | None = None,
    market: str | None = None,
    doc_types: list[str] | None = None,
    since: datetime | None = None,
    user_id: uuid.UUID | None = None,
    ef_search: int = 100,
) -> list[tuple[RagChunk, RagDocument]]:
    # 풀 오염 방지: 트랜잭션 로컬 ef_search
    await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))

    distance = RagChunk.embedding.cosine_distance(qvec)
    stmt = select(RagChunk, RagDocument).join(RagDocument, RagChunk.doc_id == RagDocument.doc_id)
    stmt = _apply_filters(
        stmt, symbols=symbols, market=market, doc_types=doc_types, since=since, user_id=user_id
    )
    stmt = stmt.order_by(distance).limit(k)
    res = await session.execute(stmt)
    return [(row[0], row[1]) for row in res.all()]


async def keyword_search(
    session: AsyncSession,
    query: str,
    *,
    k: int = 30,
    symbols: list[str] | None = None,
    market: str | None = None,
    doc_types: list[str] | None = None,
    since: datetime | None = None,
    user_id: uuid.UUID | None = None,
) -> list[tuple[RagChunk, RagDocument]]:
    """BM25 유사(tsvector @@ websearch_to_tsquery) 키워드 검색 — 하이브리드의 한 축(설계서 §5.2)."""
    tsq = func.websearch_to_tsquery("simple", query)
    rank = func.ts_rank(RagChunk.content_tsv, tsq)
    stmt = select(RagChunk, RagDocument).join(RagDocument, RagChunk.doc_id == RagDocument.doc_id)
    stmt = stmt.where(RagChunk.content_tsv.op("@@")(tsq))
    stmt = _apply_filters(
        stmt, symbols=symbols, market=market, doc_types=doc_types, since=since, user_id=user_id
    )
    stmt = stmt.order_by(rank.desc()).limit(k)
    res = await session.execute(stmt)
    return [(row[0], row[1]) for row in res.all()]
