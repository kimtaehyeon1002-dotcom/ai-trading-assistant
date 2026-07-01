"""하이브리드 검색 — 벡터 ANN + BM25 → RRF 융합 → rerank-2.5 → 시간가중. 설계서 §5.1/§5.2.

후보를 벡터·키워드 두 축으로 모아 RRF로 융합하고, Voyage rerank로 정밀 재랭킹한 뒤
신선도(시간가중)를 곱해 최종 정렬한다. 개인 노트 격리(owner_user_id)는 store 필터에서 적용.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.data_providers.normalization import now_utc, to_utc
from app.models.rag import RagChunk, RagDocument
from app.rag import rerank as RR
from app.rag import store
from app.rag.embeddings import get_voyage

log = get_logger("retrieve")


async def hybrid_search(
    session: AsyncSession,
    query: str,
    *,
    user_id: uuid.UUID | None = None,
    symbols: list[str] | None = None,
    market: str | None = None,
    doc_types: list[str] | None = None,
    since: datetime | None = None,
    k: int = 8,
    candidate_k: int = 30,
    style: str | None = None,
    use_rerank: bool | None = None,
) -> list[tuple[RagChunk, RagDocument]]:
    q = (query or "").strip()
    if not q:
        return []

    voyage = get_voyage()
    qvec = await voyage.embed_one(q, input_type="query")
    vec_rows = await store.vector_search(
        session, qvec, k=candidate_k, symbols=symbols, market=market,
        doc_types=doc_types, since=since, user_id=user_id,
    )
    try:
        kw_rows = await store.keyword_search(
            session, q, k=candidate_k, symbols=symbols, market=market,
            doc_types=doc_types, since=since, user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001 - 키워드 인덱스 미가용 시 벡터만으로 진행
        log.warning("keyword_search_failed", error=str(exc))
        kw_rows = []

    cand: dict[int, tuple[RagChunk, RagDocument]] = {}
    for chunk, doc in [*vec_rows, *kw_rows]:
        cand[chunk.chunk_id] = (chunk, doc)
    if not cand:
        return []

    # RRF 융합(두 랭킹)
    rrf = RR.rrf_fuse([[c.chunk_id for c, _ in vec_rows], [c.chunk_id for c, _ in kw_rows]])
    ordered = sorted(cand.keys(), key=lambda cid: -rrf.get(cid, 0.0))[:candidate_k]

    # rerank-2.5(가능 시) — 후보 본문으로 정밀 점수
    use = settings.rag_use_rerank if use_rerank is None else use_rerank
    if use:
        docs = [cand[cid][0].content for cid in ordered]
        rr = await RR.get_reranker().rerank(q, docs)
        base_score = {ordered[i]: s for i, s in rr}
    else:
        base_score = {cid: rrf.get(cid, 0.0) for cid in ordered}

    # 시간가중 곱
    now = now_utc()
    scored: list[tuple[int, float]] = []
    for cid in ordered:
        _chunk, doc = cand[cid]
        age_days = 0.0
        if doc.published_at:
            age_days = (now - to_utc(doc.published_at)).days
        tw = RR.time_weight(age_days, doc_type=doc.doc_type, style=style)
        scored.append((cid, base_score.get(cid, 0.0) * tw))
    scored.sort(key=lambda x: -x[1])

    return [cand[cid] for cid, _ in scored[:k]]
