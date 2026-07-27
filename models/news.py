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
    # ── design/24 Phase A 확장 — 영어 기사 한글 번역 캐시. lang == "ko"면 항상 None(번역 불필요).
    # None = 미번역(원문 폴백), ""는 원문 summary가 애초에 빈 문자열이었던 정상 케이스와 구분되지
    # 않으므로 두지 않는다 — calculators/news_translate.translate_missing이 all-or-nothing으로
    # title_ko·summary_ko를 함께 채운다(부분 실패 시 다음 실행 재시도, 절반만 캐시하지 않음).
    title_ko: str | None = None
    summary_ko: str | None = None

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
            "title_ko": self.title_ko,
            "summary_ko": self.summary_ko,
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
            title_ko=d.get("title_ko"),
            summary_ko=d.get("summary_ko"),
        )
