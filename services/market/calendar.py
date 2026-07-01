"""경제 캘린더 — data/economic_calendar.json(수기 큐레이션). 무료 API 연동은 향후 확장점."""
from __future__ import annotations

from config.settings import DATA_DIR
from core.dates import today_str
from core.jsonio import load_json
from models.market import EconomicEvent


def get_economic_calendar(limit: int = 15) -> list[EconomicEvent]:
    raw = load_json(DATA_DIR / "economic_calendar.json", default=[]) or []
    today = today_str()
    events = [EconomicEvent(**e) for e in raw if isinstance(e, dict)]
    upcoming = [e for e in events if e.date >= today]
    upcoming.sort(key=lambda e: (e.date, e.time))
    return upcoming[:limit]
