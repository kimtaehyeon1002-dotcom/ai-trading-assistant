"""Phase 6 자리 — RAG(embeddings/chunking/store/ingest/retrieve/rerank).

Voyage voyage-3.5(1024D 고정) → pgvector HNSW(m=16, ef_construction=200, cosine),
하이브리드(BM25+벡터+RRF)+rerank-2.5+시간가중. 설계서 §5.
"""
