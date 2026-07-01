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
        )
