"""실현손익(완료 매매) TR 조회 — raw dict 반환(모델 변환은 repositories/trade_repository).

KOA: opt10073(일자별종목별실현손익상세). opt10074는 일자별 '합계'만 반환해 종목 정보가 없다.
입력 3개(계좌번호/시작일자/종료일자) 모두 필수 — 종료일자를 빼면 0건으로 조용히 실패한다.
필드 읽기는 OnReceiveTrData 콜백 안에서만 유효(api.comm_rq의 fields 인자 경유).
필드명은 KOA Studio 기준이며 실계좌 응답에 따라 후보 중 값이 있는 것을 쓴다.
"""
from __future__ import annotations

from collectors.kiwoom_desktop.api import KiwoomAPI
from utils.dates import now_kst
from utils.logging import get_logger

log = get_logger("collectors.kiwoom_orders")

TR_CODE = "opt10073"
RQ_NAME = "opt10073_req"

# 표준 키 → 실계좌 응답에서 시도할 후보 필드명(값이 있는 첫 번째 사용)
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "일자": ("일자",),
    "종목코드": ("종목코드",),
    "종목명": ("종목명",),
    "매입단가": ("매입단가", "매입가"),
    "체결단가": ("체결단가", "체결가", "당일매도단가"),
    "수량": ("수량", "체결량", "당일매도수량"),
    "보유일수": ("보유일수",),
}
_ALL_FIELDS = [f for cands in _FIELD_CANDIDATES.values() for f in cands]


def _pick(row: dict, candidates: tuple[str, ...]) -> str:
    for f in candidates:
        if row.get(f):
            return row[f]
    return ""


def fetch_realized(
    api: KiwoomAPI, account: str, start_date: str, end_date: str | None = None
) -> list[dict]:
    """일자별 종목별 실현손익 raw rows. start_date/end_date=YYYYMMDD."""
    end = end_date or now_kst().strftime("%Y%m%d")
    api.set_input("계좌번호", account)
    api.set_input("시작일자", start_date)
    api.set_input("종료일자", end)
    meta = api.comm_rq(RQ_NAME, TR_CODE, fields=_ALL_FIELDS)
    rows = [
        {key: _pick(raw, cands) for key, cands in _FIELD_CANDIDATES.items()}
        for raw in meta.get("rows", [])
    ]
    if meta.get("rows"):
        log.info("첫 행 raw(필드 검증용): %s", meta["rows"][0])
    log.info("실현손익 %d건 조회 (%s~%s)", len(rows), start_date, end)
    return rows
