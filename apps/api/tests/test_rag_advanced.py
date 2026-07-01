"""Phase 6 — RAG 융합/시간가중/품질지표(순수). 오프라인 실행 가능.

retrieve/store는 sqlalchemy 의존 → Docker. rerank(순수부분)/evaluate(지표)는 stdlib만.
"""
from __future__ import annotations

from app.rag.evaluate import mrr, recall_at_k
from app.rag.rerank import rrf_fuse, time_weight


def test_rrf_fuse_combines_rankings():
    vec = ["a", "b", "c"]
    kw = ["b", "d", "a"]
    scores = rrf_fuse([vec, kw])
    # b는 양쪽 상위 → 최고점
    ranked = sorted(scores, key=lambda k: -scores[k])
    assert ranked[0] == "b"
    assert set(scores) == {"a", "b", "c", "d"}


def test_rrf_stub_reranker_overlap():
    from app.rag.rerank import _stub_rerank

    docs = ["삼성전자 실적 발표", "애플 신제품", "삼성전자 반도체 실적"]
    res = _stub_rerank("삼성전자 실적", docs)
    assert res[0][0] in (0, 2)  # 겹침 큰 문서가 상위


def test_time_weight_decay_and_doctype():
    assert time_weight(0) == 1.0
    assert time_weight(-5) == 1.0  # 음수 클램프
    assert time_weight(10, doc_type="news") < time_weight(10, doc_type="report")  # 뉴스가 빨리 감쇠
    assert time_weight(10, style="scalping") < time_weight(10, style="long")
    # 단조 감소
    assert time_weight(1) > time_weight(5) > time_weight(30)


def test_recall_and_mrr():
    retrieved = ["d1", "d2", "d3", "d4"]
    relevant = {"d2", "d4"}
    assert recall_at_k(retrieved, relevant, 2) == 0.5  # d2만 상위2
    assert recall_at_k(retrieved, relevant, 4) == 1.0
    assert mrr(retrieved, relevant) == 0.5  # 첫 관련은 2위
    assert mrr(["x", "y"], relevant) == 0.0
    assert recall_at_k(["a"], set(), 1) == 0.0
