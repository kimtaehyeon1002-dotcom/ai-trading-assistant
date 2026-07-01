"""Voyage 임베딩 래퍼 — voyage-3.5(1024D 고정). 설계서 §5.2.

- 비대칭 임베딩: input_type = 'document'(적재) / 'query'(검색).
- VOYAGE_API_KEY 없으면 '스텁 모드' — content_hash 시드로 결정적 의사 임베딩 생성
  (네트워크 없이 ingest/search 경로 검증 가능, 동일 텍스트→동일 벡터).
- content_hash로 임베딩 중복 호출을 줄인다(상위 dedup은 rag_document.content_hash).
"""
from __future__ import annotations

import hashlib
import math

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("embeddings")

EMBED_DIM = settings.embed_dim
VOYAGE_MODEL = settings.voyage_model


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stub_embed(text: str) -> list[float]:
    """결정적 의사 임베딩 — sha256 시드 기반 단위벡터(코사인 검색 경로 검증용)."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    vec: list[float] = []
    x = seed or 1
    for _ in range(EMBED_DIM):
        # 선형합동난수(결정적) → [-1,1)
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        vec.append((x / 0x3FFFFFFF) - 1.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class VoyageClient:
    def __init__(self) -> None:
        self._key = settings.voyage_api_key
        self.model = VOYAGE_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        if not self.enabled:
            return [_stub_embed(t) for t in texts]
        import httpx

        payload = {"model": self.model, "input": texts, "input_type": input_type}
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.voyage_base_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # Voyage 응답: {"data":[{"embedding":[...], "index":i}, ...]}
        ordered = sorted(data["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in ordered]

    async def embed_one(self, text: str, *, input_type: str = "query") -> list[float]:
        return (await self.embed([text], input_type=input_type))[0]


_voyage: VoyageClient | None = None


def get_voyage() -> VoyageClient:
    global _voyage
    if _voyage is None:
        _voyage = VoyageClient()
    return _voyage
