"""신선도 판정 문턱(행별 fresh_max/stale_min, 분) — design/21 §6-2 실측표가 수치의 단일 진실.

freshness.js는 이 값을 자체적으로 계산하지 않고 data-fresh-max-min/data-stale-min-min
속성으로 전달받아 소비한다(design/22 §5-2 계약 — 모듈 내부에 T·3T 공식을 하드코딩하지 않음).
행이 늘어날 때마다(시세·환율·야간선물 등) 이 표에 추가한다.
"""
from __future__ import annotations

# key: (fresh_max_min, stale_min_min) — DELAYED는 두 값 사이 구간
THRESHOLDS: dict[str, tuple[int, int]] = {
    # TA/재무(일봉·EOD) — design/21 §6-2: FRESH<24h, DELAYED 24~72h, STALE≥72h
    "ta_eod": (24 * 60, 72 * 60),
    # macro 지표·금리 — design/21 §6-2: FRESH≤120분, DELAYED 120~180분, STALE>180분
    "macro": (120, 180),
    # 종목 랭킹(design/21 §225 "마감 EOD 스냅샷으로 축소") — ta_eod와 동일 문턱 재사용
    "stock_ranking": (24 * 60, 72 * 60),
}
