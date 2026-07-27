"""자산 스냅샷 로컬 원장 — data/snapshots/(design/20 Phase 8, 절대 커밋 금지).

일 1행 append. 전일 대비·90일 추이는 이 로컬 원장에서만 계산되고, 공개 채널에는 암호문
payload 내부에만 실린다(design/20 Phase 8 DoD 7) — 원장 파일 자체는 절대 공개 저장소에
커밋되지 않는다(.gitignore의 `data/snapshots/` 규칙 + scripts/check_no_plaintext_assets.py가
이중 방어선). data/cache/(공개 커밋 대상)와 절대 혼동하지 않는다.
"""
from __future__ import annotations

from pathlib import Path

from utils.dates import now_kst
from utils.jsonio import load_json, save_json

SNAPSHOT_DIR = Path("data/snapshots")
_FILE = SNAPSHOT_DIR / "history.json"


def _read_all() -> list[dict]:
    return load_json(_FILE, default=[]) or []


def append_snapshot(total_assets_krw: float | None, accounts_krw: dict[str, float | None]) -> bool:
    """오늘 날짜로 1행 append(같은 날 재실행 시 마지막 값을 덮어써 하루 여러 빌드에 대응).

    **완전한 행만 기록한다.** total이 None(확보 0건)이면 거부하고, 계좌 일부가 결측인 날은
    호출자가 아예 부르지 않는다(generators/asset). 결측분만큼 낮은 합계가 원장에 남으면
    다음 날 전일 대비가 그 값을 기준으로 계산돼, 수집 실패가 자산 급락으로 둔갑한다.
    빠진 날은 행이 없는 채로 두고 추이 차트가 그 구간을 비우는 편이 정직하다.
    반환=기록 여부.
    """
    if total_assets_krw is None:
        return False
    today = now_kst().strftime("%Y-%m-%d")
    rows = [r for r in _read_all() if r["date"] != today]
    rows.append({"date": today, "total_assets_krw": total_assets_krw, "accounts": accounts_krw})
    rows.sort(key=lambda r: r["date"])
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    save_json(_FILE, rows)
    return True


def history(days: int = 90) -> list[dict]:
    return _read_all()[-days:]


def previous_snapshot() -> dict | None:
    """오늘을 제외한 가장 최근 스냅샷 — 전일 대비 계산 재료."""
    today = now_kst().strftime("%Y-%m-%d")
    prior = [r for r in _read_all() if r["date"] != today]
    return prior[-1] if prior else None
