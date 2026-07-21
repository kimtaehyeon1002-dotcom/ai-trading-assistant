"""ECOS(한국은행 경제통계시스템) 수집 — 기준금리.

ECOS_API_KEY 미설정 시 사실대로 None. 무료 키 발급: https://ecos.bok.or.kr/api

★ 범위 축소(정직한 고지): 국고채 3년/10년 수익률 통계표코드는 API 키 없이 실호출 검증이
불가능해(design 원칙 — 확인 안 된 코드로 "작동하는 척"하는 기능을 만들지 않는다) 이번 범위에서
제외한다. 기준금리(통계표코드 722Y001)만 구현하며, 이 코드도 실제 키 발급 후 응답으로
1회 검증이 필요하다(design/20 Phase 6 리스크·롤백 — "소스 API 스키마 변경 → 실패 시 카드 생략").
"""
from __future__ import annotations

from config.settings import ECOS_API_KEY
from utils.logging import get_logger

log = get_logger("collectors.ecos")

_BASE = "https://ecos.bok.or.kr/api"
BASE_RATE_STAT_CODE = "722Y001"  # 한국은행 기준금리(월별) — 실키 발급 후 응답 재검증 필요


def enabled() -> bool:
    return bool(ECOS_API_KEY)


def collect_base_rate(start: str, end: str) -> list[dict] | None:
    """[{'date': 'YYYYMM', 'value': float}, ...] 오름차순 — 실패 시 None. start/end: 'YYYYMM'."""
    if not enabled():
        return None
    import requests

    url = f"{_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr/1/24/{BASE_RATE_STAT_CODE}/M/{start}/{end}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("ECOS 호출 실패: %s", exc)
        return None

    rows_raw = data.get("StatisticSearch", {}).get("row")
    if not rows_raw:
        # ECOS는 오류도 200으로 응답하며 "RESULT" 키에 담는다 — 사실대로 로그만 남기고 None
        err = data.get("RESULT", {}).get("MESSAGE", "알 수 없는 응답 형식")
        log.warning("ECOS 기준금리 응답에 데이터 없음: %s", err)
        return None

    rows = []
    for r_ in rows_raw:
        try:
            rows.append({"date": r_["TIME"], "value": float(r_["DATA_VALUE"])})
        except (KeyError, ValueError, TypeError):
            continue
    return rows or None


def collect() -> dict | None:
    from datetime import datetime

    now = datetime.now()
    start = f"{now.year - 2}{now.month:02d}"
    end = f"{now.year}{now.month:02d}"
    obs = collect_base_rate(start, end)
    return {"base_rate": obs} if obs else None
