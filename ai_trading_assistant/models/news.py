"""뉴스 dataclass — 제목/출처/시각/카테고리/요약/링크(본문 미저장)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str = ""
    published: datetime | None = None
    summary: str = ""
    region: str = ""  # KR | US
    lang: str = "ko"
    categories: list[str] = field(default_factory=list)
    # ── design/20 Phase 5 확장 필드 — 전부 기본값 있어 기존 생성 호출 하위호환 ──
    level: str = "L1"  # L1(참고)|L2(주목)|L3(필수) — calculators/news_levels.assign_levels가 부여
    impact_tags: list[dict] = field(default_factory=list)  # [{ticker, name, market}, ...]
    first_seen_at: str | None = None  # 저장소 최초 병합 시각(UTC ISO) — 재병합 시 덮어쓰지 않음

    @property
    def id(self) -> str:
        return hashlib.sha256(self.link.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
            "region": self.region,
            "lang": self.lang,
            "categories": self.categories,
            "level": self.level,
            "impact_tags": self.impact_tags,
            "first_seen_at": self.first_seen_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NewsArticle":
        pub = d.get("published")
        return cls(
            title=d.get("title", ""),
            link=d.get("link", ""),
            source=d.get("source", ""),
            published=datetime.fromisoformat(pub) if pub else None,
            summary=d.get("summary", ""),
            region=d.get("region", ""),
            lang=d.get("lang", "ko"),
            categories=d.get("categories", []),
            level=d.get("level", "L1"),
            impact_tags=d.get("impact_tags", []),
            first_seen_at=d.get("first_seen_at"),
        )
