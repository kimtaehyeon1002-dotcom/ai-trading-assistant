"""RAG 서비스 — 뉴스 인입(저작권 안전) + 벡터검색 + 인용 조립. 설계서 §2.4, §5.

인입: 뉴스 제목+자체요약만 저장(본문 미적재) → 청킹 → voyage 임베딩(document) → pgvector.
검색: 쿼리 임베딩(query) → 코사인 ANN + 권한/메타 필터 → 인용 메타 조립(url 기준 dedup).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.data_providers.errors import ProviderError
from app.data_providers.normalization import now_utc
from app.rag import retrieve, store
from app.rag.chunking import chunk_text
from app.rag.embeddings import content_hash, get_voyage
from app.services import market_service

log = get_logger("rag")


async def ingest_news(
    session: AsyncSession,
    *,
    market: str | None = None,
    symbols: list[str] | None = None,
    lang: str | None = None,
    limit: int = 20,
) -> dict:
    """최근 뉴스 헤드라인+요약을 RAG에 적재(본문 미저장). 중복(content_hash)은 건너뜀."""
    try:
        items = await market_service.get_news(market, symbols, lang, limit)
    except ProviderError as exc:
        log.warning("rag_ingest_news_unavailable", error=str(exc))
        return {"ingested": 0, "skipped": 0, "source_unavailable": True}

    voyage = get_voyage()
    ingested = 0
    skipped = 0
    for it in items:
        body = it.summary or ""  # 본문 아님 — 자체요약만
        content_for_hash = f"{it.url}␟{it.title}"
        chash = content_hash(content_for_hash)
        if await store.get_document_by_hash(session, chash):
            skipped += 1
            continue

        syms = it.symbols or (symbols or [])
        date_str = it.published_at.date().isoformat() if it.published_at else None
        chunks = chunk_text(
            f"{it.title}\n{body}".strip(),
            doc_type="news",
            title=it.title,
            date=date_str,
            symbols=syms,
        )
        embeddings = await voyage.embed([c.content for c in chunks], input_type="document")
        await store.add_document_with_chunks(
            session,
            source_table="news_article",
            source_pk=it.id,
            doc_type="news",
            title=it.title,
            url=it.url,
            language=it.language,
            market=market,
            published_at=it.published_at,
            content_hash=chash,
            instrument_id=None,
            symbols=syms,
            chunks=chunks,
            embeddings=embeddings,
            embed_model=voyage.model,
            is_public=True,
            license_ok=True,
        )
        ingested += 1

    return {"ingested": ingested, "skipped": skipped}


def _source_label(url: str | None) -> str:
    if not url:
        return "rag"
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "") or "rag"
    except Exception:  # noqa: BLE001
        return "rag"


async def search(
    session: AsyncSession,
    query: str,
    *,
    user_id: uuid.UUID | None = None,
    symbols: list[str] | None = None,
    market: str | None = None,
    doc_types: list[str] | None = None,
    since: datetime | None = None,
    k: int = 8,
    style: str | None = None,
) -> list[dict]:
    """하이브리드 검색(벡터+BM25+RRF+rerank+시간가중) → 인용 메타(url dedup). 빈 쿼리/오류는 빈 리스트."""
    q = (query or "").strip()
    if not q:
        return []
    rows = await retrieve.hybrid_search(
        session,
        q,
        user_id=user_id,
        symbols=symbols,
        market=market,
        doc_types=doc_types,
        since=since,
        k=k,
        style=style,
    )

    out: list[dict] = []
    seen: set[str] = set()
    for chunk, doc in rows:
        key = doc.url or str(doc.doc_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "title": doc.title,
                "url": doc.url,
                "source": _source_label(doc.url),
                "published_at": doc.published_at,
                "doc_type": doc.doc_type,
                "snippet": chunk.content[:240],
            }
        )
    return out


async def ingest_note(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    title: str | None,
    text: str,
    symbols: list[str] | None = None,
    market: str | None = None,
) -> dict:
    """개인 노트 인입(owner_user_id, is_public=False) — 본인만 검색됨(설계서 §5.3 RLS)."""
    content = f"{title}\n{text}".strip() if title else (text or "").strip()
    if not content:
        return {"ingested": 0, "skipped": 0}
    chash = content_hash(f"note:{user_id}:{title}:{text}")
    if await store.get_document_by_hash(session, chash):
        return {"ingested": 0, "skipped": 1}
    voyage = get_voyage()
    chunks = chunk_text(content, doc_type="note", title=title, symbols=symbols)
    embeddings = await voyage.embed([c.content for c in chunks], input_type="document")
    await store.add_document_with_chunks(
        session,
        source_table="user_note",
        source_pk=str(uuid.uuid4()),
        doc_type="note",
        title=title,
        url=None,
        language="ko",
        market=market,
        published_at=now_utc(),
        content_hash=chash,
        instrument_id=None,
        symbols=symbols or [],
        chunks=chunks,
        embeddings=embeddings,
        embed_model=voyage.model,
        owner_user_id=user_id,
        is_public=False,
        license_ok=True,
    )
    return {"ingested": 1, "skipped": 0}
