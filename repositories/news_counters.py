"""일별 게재 카운터 — 자정(KST) 리셋, 유니크 수집 수·게재 수 누적(design/20 Phase 5, design/21 §2-3).

30분마다 도는 news 빌드는 매번 RSS의 현재 스냅샷만 보므로, "오늘 수집 총량"은 하루 동안의
빌드에서 등장한 유니크 기사 ID를 누적해야 한다. 날짜(KST)가 바뀌면 새로 시작한다.
"""
from __future__ import annotations

from config.settings import CACHE_DIR
from utils.dates import today_str
from utils.jsonio import load_json, save_json

_STORE = CACHE_DIR / "news_counters.json"


def update(collected_ids: set[str], published_ids: set[str]) -> dict:
    """이번 빌드의 수집/게재 ID 집합을 오늘자 누적에 병합하고 {collected_total, published_total} 반환."""
    today = today_str()
    data = load_json(_STORE, default={}) or {}
    if data.get("date") != today:
        data = {"date": today, "collected_ids": [], "published_ids": []}

    collected = set(data.get("collected_ids", [])) | collected_ids
    published = set(data.get("published_ids", [])) | published_ids
    save_json(_STORE, {"date": today, "collected_ids": sorted(collected), "published_ids": sorted(published)})
    return {"collected_total": len(collected), "published_total": len(published)}
