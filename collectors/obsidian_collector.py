"""Obsidian vault 수집 — 워치리스트(vault/00_Watchlist/*.md)의 단일 진실원.

다운로드 없음, 로컬 파일 스캔만(정규화는 repositories/obsidian_repository). vault 폴더가
없거나 비어 있으면 None 반환(= skipped, 가짜 데이터 생성 금지). 결과는
cache/vault_watchlist.json 에 요약 저장.
"""
from __future__ import annotations

from config.settings import CACHE_DIR, VAULT_WATCHLIST_DIR
from utils.dates import now_kst
from utils.frontmatter import parse as parse_frontmatter
from utils.jsonio import save_json
from utils.logging import get_logger

log = get_logger("collectors.obsidian")

_CACHE = CACHE_DIR / "vault_watchlist.json"


def enabled() -> bool:
    return VAULT_WATCHLIST_DIR.is_dir() and any(VAULT_WATCHLIST_DIR.glob("*.md"))


def collect() -> dict[str, list[dict]] | None:
    """{"watchlist": [frontmatter dict, ...]} — 미설정 시 None(skipped)."""
    if not enabled():
        return None
    rows: list[dict] = []
    for path in sorted(VAULT_WATCHLIST_DIR.glob("*.md")):
        try:
            fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError as exc:  # noqa: BLE001 - 노트 1개 실패로 전체 중단 금지
            log.warning("vault 노트 읽기 실패 %s: %s", path.name, exc)
            continue
        if fm:
            rows.append(fm)
    out = {"watchlist": rows}
    save_json(_CACHE, {"as_of": now_kst().isoformat(), "databases": {k: len(v) for k, v in out.items()}})
    return out
