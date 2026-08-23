"""ECOS(한국은행 경제통계시스템) 수집 — 기준금리.

ECOS_API_KEY 미설정 시 사실대로 None. 무료 키 발급: https://ecos.bok.or.kr/api

★ 범위 축소(정직한 고지): 국고채 3년/10년 수익률 통계표코드는 API 키 없이 실호출 검증이
불가능해(design 원칙 — 확인 안 된 코드로 "작동하는 척"하는 기능을 만들지 않는다) 이번 범위에서
제외한다. 기준금리(통계표코드 722Y001)만 구현한다.

실키 검증 완료(2026-08-13) — 그리고 그 검증에서 **틀린 값을 뱉는 버그**가 드러났다.
722Y001은 "한국은행 기준금리 및 여수신금리" 통계표로 기준금리 하나가 아니라 여러 항목
(0101000 기준금리, 0102000 자금조정예금금리, 0104000 자금조정대출금리 …)을 함께 담는다.
항목코드를 빼고 조회하면 ECOS는 전 항목을 시점별로 섞어 돌려주고(같은 조건에서
list_total_count=216), 앞 24행만 받아 마지막 행을 최신값으로 쓰던 종전 코드는 2024년 10월의
**다른 항목** 값 1.75를 "현재 기준금리"로 발행했다. URL 끝에 항목코드를 붙여야 단일 계열이 온다.
"""
from __future__ import annotations

from config.settings import ECOS_API_KEY
from utils.logging import get_logger

log = get_logger("collectors.ecos")

_BASE = "https://ecos.bok.or.kr/api"
BASE_RATE_STAT_CODE = "722Y001"  # "한국은행 기준금리 및 여수신금리"(월별) — 다항목 통계표
BASE_RATE_ITEM_CODE = "0101000"  # 그 안의 "한국은행 기준금리" 항목(실호출 검증 2026-08-13)


def enabled() -> bool:
    return bool(ECOS_API_KEY)


def collect_base_rate(start: str, end: str) -> list[dict] | None:
    """[{'date': 'YYYYMM', 'value': float}, ...] 오름차순 — 실패 시 None. start/end: 'YYYYMM'."""
    if not enabled():
        return None
    import requests

    url = (
        f"{_BASE}/StatisticSearch/{ECOS_API_KEY}/json/kr/1/24"
        f"/{BASE_RATE_STAT_CODE}/M/{start}/{end}/{BASE_RATE_ITEM_CODE}"
    )
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
        # 항목코드를 URL에 넣었어도 응답에서 한 번 더 거른다 — 이 수집기가 실제로 틀렸던 방식이
        # "여러 항목이 섞여 오는데 그걸 한 계열로 취급"이었다. 필터가 있으면 같은 사고가
        # 나더라도 틀린 값을 발행하는 대신 결측이 된다(가짜 데이터보다 빈칸이 낫다).
        if r_.get("ITEM_CODE1") not in (BASE_RATE_ITEM_CODE, None):
            continue
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
