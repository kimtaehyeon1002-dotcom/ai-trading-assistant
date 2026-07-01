"""Phase 2.5 최소 RAG — 청킹/임베딩 스텁/인용 라벨 단위 테스트.

embeddings/rag_service는 config(pydantic-settings)·sqlalchemy 의존 → Docker/uv 환경에서 실행.
chunking은 stdlib만 의존 → 오프라인 실행 가능.
"""
from __future__ import annotations

from app.rag.chunking import chunk_text


def test_chunk_news_single_with_header():
    chunks = chunk_text(
        "삼성전자 신제품 공개\n시장 반응 요약입니다.",
        doc_type="news",
        title="삼성전자 신제품 공개",
        date="2026-06-23",
        symbols=["005930.KS"],
    )
    assert len(chunks) == 1
    head = chunks[0].content.splitlines()[0]
    assert "005930.KS" in head and "news" in head and "2026-06-23" in head


def test_chunk_long_text_splits_with_overlap():
    body = "가" * 3000
    chunks = chunk_text(body, doc_type="filing", title="사업보고서")
    assert len(chunks) >= 2
    assert all(c.content.startswith("[") for c in chunks)  # 헤더 주입
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_stub_embedding_deterministic_unit_vector():
    from app.rag.embeddings import EMBED_DIM, _stub_embed

    a = _stub_embed("삼성전자")
    b = _stub_embed("삼성전자")
    c = _stub_embed("카카오")
    assert a == b and a != c
    assert len(a) == EMBED_DIM
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_source_label_from_url():
    from app.services.rag_service import _source_label

    assert _source_label("https://www.example.com/news/1") == "example.com"
    assert _source_label(None) == "rag"
