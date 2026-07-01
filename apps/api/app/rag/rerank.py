"""RAG 융합·재랭킹·시간가중 — RRF + Voyage rerank-2.5 + 신선도 감쇠. 설계서 §5.2.

순수 함수(rrf_fuse·time_weight)는 stdlib만 → 오프라인 단위 테스트 가능.
VoyageReranker는 rerank-2.5 호출(키 없으면 토큰 겹침 기반 결정적 스텁).
"""
from __future__ import annotations

import math
import re

RRF_K = 60

# 신선도 감쇠 λ(클수록 빨리 감쇠) — 뉴스 > 노트 > 공시 > 리포트
LAMBDA_BY_DOCTYPE: dict[str, float] = {
    "news": 0.08,
    "note": 0.05,
    "filing": 0.02,
    "report": 0.015,
    "default": 0.04,
}
# 스타일별 배수(단타는 더 빨리 감쇠, 장기는 천천히)
_STYLE_MULT = {"scalping": 1.5, "swing": 1.0, "long": 0.5}


def rrf_fuse(rankings: list[list[str]], *, k: int = RRF_K) -> dict[str, float]:
    """여러 랭킹 리스트(키 순서)를 Reciprocal Rank Fusion으로 합성 → key→score."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return scores


def time_weight(age_days: float, *, doc_type: str = "default", style: str | None = None) -> float:
    """exp(-λ·age) 신선도 가중(0~1). age<0은 0으로 클램프."""
    lam = LAMBDA_BY_DOCTYPE.get(doc_type, LAMBDA_BY_DOCTYPE["default"])
    lam *= _STYLE_MULT.get(style or "swing", 1.0)
    if age_days < 0:
        age_days = 0.0
    return math.exp(-lam * age_days)


_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")


def _stub_rerank(query: str, documents: list[str]) -> list[tuple[int, float]]:
    """토큰 겹침(Jaccard 유사) 기반 결정적 스텁 점수."""
    q = set(_TOKEN.findall(query.lower()))
    out: list[tuple[int, float]] = []
    for i, d in enumerate(documents):
        dt = set(_TOKEN.findall(d.lower()))
        inter = len(q & dt)
        union = len(q | dt) or 1
        out.append((i, inter / union))
    out.sort(key=lambda x: -x[1])
    return out


class VoyageReranker:
    def __init__(self) -> None:
        from app.core.config import settings

        self._key = settings.voyage_api_key
        self.model = settings.voyage_rerank_model

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def rerank(
        self, query: str, documents: list[str], *, top_k: int | None = None
    ) -> list[tuple[int, float]]:
        """(원본 index, relevance_score) 내림차순. 키 없으면 스텁."""
        if not documents:
            return []
        if not self.enabled:
            res = _stub_rerank(query, documents)
            return res[:top_k] if top_k else res
        import httpx

        from app.core.config import settings

        payload = {"model": self.model, "query": query, "documents": documents}
        if top_k:
            payload["top_k"] = top_k
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.voyage_rerank_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        results = [(r["index"], r.get("relevance_score", 0.0)) for r in data.get("data", [])]
        results.sort(key=lambda x: -x[1])
        return results


_reranker: VoyageReranker | None = None


def get_reranker() -> VoyageReranker:
    global _reranker
    if _reranker is None:
        _reranker = VoyageReranker()
    return _reranker
