"""Notion 수집 — 사용자 관리 투자 데이터(자산/목표/워치리스트/현금흐름)의 단일 진실원.

다운로드만 담당(정규화는 repositories/notion_repository). 토큰/DB id 미설정이면 None 반환
(= skipped, 가짜 데이터 생성 금지). 결과는 cache/notion_assets.json 에 저장.
"""
from __future__ import annotations

from config.settings import CACHE_DIR, NOTION_API_KEY, NOTION_DATABASES, NOTION_VERSION
from utils.dates import now_kst
from utils.jsonio import save_json
from utils.logging import get_logger

log = get_logger("collectors.notion")

_CACHE = CACHE_DIR / "notion_assets.json"


def enabled() -> bool:
    return bool(NOTION_API_KEY and any(NOTION_DATABASES.values()))


def _query_db(database_id: str) -> list[dict]:
    import requests

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    rows: list[dict] = []
    cursor: str | None = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            return rows
        cursor = data.get("next_cursor")


def collect() -> dict[str, list[dict]] | None:
    """{db이름: raw pages[]} — 미설정 시 None(skipped)."""
    if not enabled():
        return None
    out: dict[str, list[dict]] = {}
    for name, db_id in NOTION_DATABASES.items():
        if not db_id:
            continue
        try:
            out[name] = _query_db(db_id)
        except Exception as exc:  # noqa: BLE001 - DB 단위 부분 실패 허용
            log.warning("notion %s 실패: %s", name, exc)
    save_json(_CACHE, {"as_of": now_kst().isoformat(), "databases": {k: len(v) for k, v in out.items()}})
    return out
