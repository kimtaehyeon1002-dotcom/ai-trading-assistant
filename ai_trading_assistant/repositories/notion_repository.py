"""Notion ERP 정규화 — raw pages(REST API) → 평평한 행 + cache/notion_erp.json 영속.

collector(다운로드)와 분리: 여기서만 Notion 응답 포맷을 안다. 토큰 미설정으로 수집이
skipped여도 마지막 캐시를 유지한다(대시보드가 최근 상태를 계속 표시).
"""
from __future__ import annotations

from config.settings import CACHE_DIR
from utils.dates import now_kst
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("repositories.notion")

_CACHE = CACHE_DIR / "notion_erp.json"


def _prop_value(p: dict):
    """Notion property(typed) → 스칼라. 미지 타입은 빈 문자열."""
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


def _rows(pages: list[dict]) -> list[dict]:
    return [
        {name: _prop_value(prop) for name, prop in page.get("properties", {}).items()}
        for page in pages
    ]


def save_normalized(raw: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """{db이름: raw pages[]} → 정규화 후 캐시 저장. 반환=정규화 결과."""
    erp = {name: _rows(pages) for name, pages in raw.items()}
    save_json(_CACHE, {"as_of": now_kst().isoformat(), "databases": erp})
    log.info("Notion ERP 정규화 저장: %s", {k: len(v) for k, v in erp.items()})
    return erp


def load_normalized() -> dict | None:
    """캐시에서 {as_of, databases:{...}} 로드. 없으면 None(대시보드 섹션 생략)."""
    data = load_json(_CACHE, default=None)
    return data if isinstance(data, dict) and data.get("databases") else None
