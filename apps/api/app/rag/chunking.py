"""유형별 청킹 — 의미경계 우선, 청크 앞에 [종목·유형·날짜] 헤더 주입. 설계서 §5.2.

MVP는 문자 길이 기준 슬라이딩 윈도(토큰 근사). 뉴스는 제목+요약이라 보통 1청크.
공시/리포트 등 장문은 윈도 분할. 표/수치 분리·parent-child 확장은 Phase 6.
"""
from __future__ import annotations

from dataclasses import dataclass

# 유형별 (목표 문자수, 오버랩) — 토큰 대략 1.5~2자/토큰 가정의 보수적 근사
_SIZES: dict[str, tuple[int, int]] = {
    "news": (700, 80),
    "filing": (1400, 140),
    "report": (1200, 160),
    "note": (600, 60),
}


@dataclass
class Chunk:
    index: int
    content: str


def _header(doc_type: str, title: str | None, date: str | None, symbols: list[str] | None) -> str:
    parts = []
    if symbols:
        parts.append("·".join(symbols[:3]))
    parts.append(doc_type)
    if date:
        parts.append(date)
    head = " ".join(p for p in parts if p)
    if title:
        return f"[{head}] {title}"
    return f"[{head}]"


def chunk_text(
    text: str,
    *,
    doc_type: str = "news",
    title: str | None = None,
    date: str | None = None,
    symbols: list[str] | None = None,
) -> list[Chunk]:
    body = (text or "").strip()
    header = _header(doc_type, title, date, symbols)
    size, overlap = _SIZES.get(doc_type, _SIZES["news"])

    if len(body) <= size:
        content = f"{header}\n{body}".strip() if body else header
        return [Chunk(index=0, content=content)]

    chunks: list[Chunk] = []
    start = 0
    idx = 0
    step = max(1, size - overlap)
    while start < len(body):
        piece = body[start : start + size]
        chunks.append(Chunk(index=idx, content=f"{header}\n{piece}".strip()))
        idx += 1
        start += step
    return chunks
