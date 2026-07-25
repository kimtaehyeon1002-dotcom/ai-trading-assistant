"""Obsidian vault 정규화 — frontmatter(이미 평평함) → cache/vault_erp.json 영속.

반환 계약은 {as_of, databases:{...}} — 이 모양을 유지하는 한 소비자(calculators/erp_stats,
generators/stock의 유니버스 병합)는 수집 소스 교체에 영향받지 않는다. vault 폴더가 비어 있어
수집이 skipped여도 마지막 캐시를 유지한다(소비자가 최근 상태를 계속 사용).
"""
from __future__ import annotations

from config.settings import CACHE_DIR
from utils.dates import now_kst
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("repositories.obsidian")

_CACHE = CACHE_DIR / "vault_erp.json"


def save_normalized(raw: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """{"watchlist": [...]} → 캐시 저장(frontmatter가 이미 평평해 정규화는 no-op).

    반환=저장된 databases.
    """
    save_json(_CACHE, {"as_of": now_kst().isoformat(), "databases": raw})
    log.info("Vault ERP 저장: %s", {k: len(v) for k, v in raw.items()})
    return raw


def load_normalized() -> dict | None:
    """캐시에서 {as_of, databases:{...}} 로드. 없으면 None(대시보드 섹션 생략)."""
    data = load_json(_CACHE, default=None)
    return data if isinstance(data, dict) and data.get("databases") else None
