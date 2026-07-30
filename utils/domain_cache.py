"""도메인 캐시 계약 — "무효 데이터가 유효 캐시를 덮지 않는다"를 구현하는 단 한 곳(design/25 Phase A).

## 왜 별도 캐시 파일이 없는가 (결정 1, 2026-07-29)

루트 `cache/`는 gitignore 대상이라 GitHub Actions에서는 매 실행이 빈 상태로 시작한다 —
거기에 캐시를 두면 last-good 보호가 **CI에서만 조용히 작동하지 않는다**(가장 나쁜 종류의 버그다).
그렇다고 캐시를 따로 커밋하면 같은 데이터가 저장소에 두 벌 남고 cron마다 커밋이 두 배가 된다.

그래서 **이미 커밋되는 발행물(`docs/data/...`)을 그대로 직전 상태로 읽는다.** 캐시 계층은
물리적 두 번째 사본이 아니라 이 모듈의 load/save 계약으로 존재한다. 스펙이 그린 "캐시와
발행물의 물리적 분리"는 포기하지만, 그 분리가 주려던 실익(수집 실패로부터 발행물 보호,
쓰기 경로 단일화)은 전부 얻는다.

## 폴백 정책 (결정 2)

**항목별 폴백 + 나이 상한.** 이번에 못 받은 항목만 직전 값으로 채우되, 그 값의 원래
`as_of`를 그대로 달아 보낸다 — 신선도 배지가 나이를 정직하게 드러내므로 낡은 값이
새 값인 척하지 않는다. 상한을 넘긴 항목은 버린다(낡은 값보다 빈칸이 낫다).
이 방식은 market_collector의 market_last.json(26h 상한)에서 이미 검증된 선례다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("utils.domain_cache")

# 항목별 폴백 상한(시간). 거시지표는 발표 주기가 길어(월간·분기) 넉넉해야 의미가 있다 —
# FRED가 하루 죽었다고 CPI 카드가 사라지면 안 된다. 반대로 무한정 끌고 가면 "언제 값인지"가
# 무의미해지므로 주 단위에서 끊는다.
DEFAULT_MAX_AGE_H = 24 * 7


def _as_of(item: dict | None) -> datetime | None:
    """항목의 기준시각. Envelope 규약상 `envelope.as_of_iso`에 있다."""
    if not isinstance(item, dict):
        return None
    raw = (item.get("envelope") or {}).get("as_of_iso") or item.get("as_of_iso")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_previous(path: Path) -> dict:
    """직전 발행물 = last-good 캐시. 없거나 형태가 다르면 빈 dict(첫 실행·손상 내성)."""
    data = load_json(path, default=None)
    return data if isinstance(data, dict) else {}


def merge_last_good(
    new: dict,
    previous: dict,
    *,
    max_age_h: float = DEFAULT_MAX_AGE_H,
    now: datetime | None = None,
) -> tuple[dict, list[str]]:
    """이번 수집에서 결측(None)인 키만 직전 값으로 채운다. → (병합결과, 폴백된 키 목록)

    새 값이 있으면 **항상 새 값이 이긴다** — 이 함수는 결측을 메울 뿐 값을 비교·판정하지 않는다
    (그건 validators의 책임이고, 여기서 또 판단하면 규칙이 두 곳으로 갈라진다).
    폴백된 항목은 원래 as_of를 유지하므로 화면의 신선도 배지가 나이를 그대로 드러낸다.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_h)
    merged = dict(new)
    carried: list[str] = []
    for key, value in new.items():
        if value is not None:
            continue
        old = previous.get(key)
        if old is None:
            continue
        stamp = _as_of(old)
        if stamp is None or stamp < cutoff:
            continue  # 나이를 알 수 없거나 상한 초과 → 결측 유지(빈칸이 낫다)
        merged[key] = old
        carried.append(key)
    return merged, carried


def save_keyed(path: Path, new: dict, *, max_age_h: float = DEFAULT_MAX_AGE_H) -> dict:
    """키-항목 매핑을 발행한다. 직전 발행물에서 결측분을 메운 뒤 저장하고, 병합 결과를 돌려준다.

    전량 결측이면 **저장 자체를 건너뛴다** — 빈 파일로 덮으면 직전 발행물까지 잃는다.
    """
    previous = load_previous(path)
    merged, carried = merge_last_good(new, previous, max_age_h=max_age_h)
    if previous and not any(v is not None for v in merged.values()):
        log.warning("%s: 전량 결측 — 직전 발행물을 유지하고 저장을 건너뛴다", path.name)
        return previous
    if carried:
        log.info("%s: 직전 값으로 채운 항목 %d개 %s", path.name, len(carried), carried)
    save_json(path, merged)
    return merged
