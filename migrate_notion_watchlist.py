"""1회성 마이그레이션: Notion 워치리스트 DB → vault/00_Watchlist/*.md

    NOTION_API_KEY=... NOTION_DB_WATCHLIST=... python migrate_notion_watchlist.py

노션 연동이 vault로 이관 완료되어 collectors/notion_collector·repositories/notion_repository는
삭제되었다. 이 스크립트는 그 두 모듈의 핵심 로직(DB 쿼리 + property 평탄화)을 자체 포함해
독립적으로 동작한다 — 실행 후에는 다시 쓸 일이 없는 1회성 도구이므로 별도 모듈로 분리하지 않는다.

이미 존재하는 vault 노트는 건드리지 않는다(사용자가 vault에서 이미 손댔을 수 있으므로
덮어쓰기 금지).
"""
from __future__ import annotations

import os
import re

import requests

from config.settings import VAULT_WATCHLIST_DIR

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")
NOTION_DB_WATCHLIST = os.getenv("NOTION_DB_WATCHLIST", "")

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def _query_db(database_id: str) -> list[dict]:
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


def _prop_value(p: dict):
    t = p.get("type", "")
    v = p.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in (v or []))
    if t == "number":
        return v
    if t == "select":
        return (v or {}).get("name", "")
    if t == "date":
        return (v or {}).get("start", "")
    if t == "checkbox":
        return bool(v)
    return ""


def _slug(name: str) -> str:
    name = _INVALID_CHARS.sub("_", str(name).strip())
    return name or "untitled"


def _fm_line(key: str, value) -> str:
    if value is None or value == "":
        return f"{key}:"
    if isinstance(value, bool):
        return f"{key}: {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key}: {value}"
    escaped = str(value).replace('"', '\\"')
    return f'{key}: "{escaped}"'


def main() -> None:
    if not NOTION_API_KEY or not NOTION_DB_WATCHLIST:
        raise SystemExit("NOTION_API_KEY/NOTION_DB_WATCHLIST 미설정 — 이관할 대상이 없습니다.")

    pages = _query_db(NOTION_DB_WATCHLIST)
    if not pages:
        print("워치리스트 DB에 페이지가 없습니다.")
        return

    VAULT_WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)
    written, skipped = 0, 0
    for page in pages:
        row = {name: _prop_value(prop) for name, prop in page.get("properties", {}).items()}
        title = row.get("종목명") or "untitled"
        path = VAULT_WATCHLIST_DIR / f"{_slug(title)}.md"
        if path.exists():
            print(f"건너뜀(이미 존재): {path.name}")
            skipped += 1
            continue

        lines = ["---", *(_fm_line(k, v) for k, v in row.items()), "---", "", f"관련 기억: [[20_Memory/stocks/{title}]]"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written += 1
        print(f"생성: {path.name}")

    print(f"완료 — 생성 {written}건, 건너뜀(기존 노트 보존) {skipped}건, 전체 {len(pages)}건")


if __name__ == "__main__":
    main()
