"""뉴스 raw 검증 — 제목/링크 필수, 링크 중복 제거, 미래 타임스탬프 제거."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def validate(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    horizon = datetime.now(timezone.utc) + timedelta(hours=1)  # 시계 오차 허용
    for r in rows:
        link = (r.get("link") or "").strip()
        title = (r.get("title") or "").strip()
        if not link or not title:
            continue
        if link in seen:
            continue
        pub = r.get("published")
        if isinstance(pub, datetime) and pub > horizon:
            r = {**r, "published": None}  # 미래 시각은 신뢰 불가 → 제거
        seen.add(link)
        out.append(r)
    return out
