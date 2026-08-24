"""랭킹 히스토리 원장 — 매 거래일의 시장 스냅샷 축적(design/28 Phase A).

이 원장이 존재하는 이유는 **소급이 불가능**하기 때문이다. FDR·yfinance 어느 쪽도 "그날의 전종목
거래대금 순위"를 과거로 돌려주지 않는다. 순위 변화(↑3/↓2/NEW)·거래량 급증(20일 평균 대비)·연속
상위 같은 축은 전부 여기 쌓인 파일에서만 나오며, 오늘 저장하지 않은 하루는 영원히 복원되지 않는다.

설계상 중요한 두 결정(design/28 §3-1·§3-2):

1. **시장별 디렉터리 분리.** stock.yml의 US 마감 실행(UTC 22:00)은 KST로 다음 날 07:00이다.
   한 파일에 KR·US를 함께 담으면 파일명의 날짜가 어느 시장의 거래일인지 영구히 모호해진다.
2. **날짜별 개별 파일.** runlog.json이 `-X theirs` rebase로 원격 기록을 잃었던 사고와 같은
   함정을 구조적으로 피한다 — 서로 다른 실행이 서로 다른 파일을 쓰므로 병합할 것이 없다.
   원장을 파일로 쪼개는 것이 병합 로직보다 싸다.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config.settings import DATA_DIR
from utils.dates import now_kst
from utils.jsonio import save_json
from utils.logging import get_logger

log = get_logger("repositories.history")

HISTORY_DIR = DATA_DIR / "history" / "rankings"

# 상위 300종목만 남긴다 — TOP30만으로는 "거래량 급증"의 모집단이 없고(급증 종목은 대개 어제까지
# 30위 밖이다), 전종목은 1년에 수백 MB가 되어 저장소가 망가진다(design/28 §3-3).
HISTORY_TOP_N = 300

# 시장별 보존 파일 수(약 1.6년). 52주 신고가 판정에 250거래일이 필요하고, 중간에 며칠 빠져도
# 윈도가 깨지지 않도록 여유를 뒀다.
KEEP_FILES = 400

_ET = ZoneInfo("America/New_York")

# 정규장 마감 + 여유. KR 15:30 → 15:35, US 16:00 ET → 16:05.
_KR_CLOSE = time(15, 35)
_US_CLOSE = time(16, 5)


def _round(v, digits: int):
    """정수로 떨어지면 정수로 쓴다 — KR 종가는 원 단위 정수라 `281500.0`의 `.0`이 300행 내내
    반복된다. 파일 크기가 상한(20KB)에 가장 근접하는 쪽이 KR이므로 이 2바이트가 여유가 된다."""
    if v is None:
        return None
    r = round(v, digits)
    return int(r) if r == int(r) else r


def _int(v):
    return None if v is None else int(v)


def _shrink(rows: list[dict]) -> list[dict]:
    """거래대금 상위 N종목의 축소 레코드. 키를 한 글자로 줄이는 것은 미학이 아니라 용량 때문이다
    (300행 × 5키의 키 문자열이 매일 반복된다). 스키마는 design/28 §3-3 표에 고정돼 있다.

    값도 함께 정리한다. yfinance는 float64를 그대로 주므로 종가가 `123.45999908447266`으로
    직렬화되는데, 이는 데이터가 아니라 부동소수 잡음이고 파일 크기의 상당 부분을 차지한다
    (실측: 반올림 전 23.3KB → 후 15.6KB). 거래대금·거래량은 소수점이 애초에 의미가 없어
    정수로 내린다.
    """
    top = sorted(rows, key=lambda r: r.get("amount") or 0, reverse=True)[:HISTORY_TOP_N]
    return [
        {
            "c": r["code"],
            "p": _round(r.get("close"), 2),
            "r": _round(r.get("change_pct"), 2),
            "v": _int(r.get("volume")),
            "a": _int(r.get("amount")),
        }
        for r in top
    ]


def kr_gate_open(now: datetime | None = None) -> bool:
    """거래일 확정(네트워크 1회)을 시도할 가치가 있는 시각인가 — 값싼 사전 조건.

    KR 거래일 확정은 지수 일봉 조회를 부른다. stock.yml은 하루 9회 도는데 그중 기록 가능성이
    있는 것은 마감 후 실행뿐이므로, 시각만으로 거를 수 있는 대다수 실행에서 호출 자체를 없앤다.
    최종 판정은 should_record_kr()가 한다 — 이 함수는 필요조건일 뿐이다.
    """
    return (now or now_kst()).time() >= _KR_CLOSE


def should_record_kr(trade_date: str | None, now: datetime | None = None) -> bool:
    """KR 원장을 지금 써도 되는가 — 장중 미완성 값으로 그날을 결산하지 않기 위한 게이트.

    조건은 "거래일이 오늘이고 마감(15:35)을 지났을 것" 하나다. 월요일 장중 실행을 생각하면 왜
    두 조건이 모두 필요한지 분명해진다: 그때 KRX 스냅샷은 월요일 실시간 값이지만 지수 일봉의
    마지막 거래일은 아직 금요일일 수 있다. 시각 조건만 보면 월요일 장중 값이 금요일 파일을
    덮어써 완결된 원장을 오염시킨다. 오염보다 결측이 낫다.
    """
    if not trade_date:
        return False
    now = now or now_kst()
    return now.date().isoformat() == trade_date and now.time() >= _KR_CLOSE


def should_record_us(trade_date: str | None, now: datetime | None = None) -> bool:
    """US 원장을 지금 써도 되는가. 기준 시각은 ET(거래일의 소속 시간대)다.

    KR과 조건이 다른 이유는 시차다. UTC 22:00 크론은 ET로 같은 날 오후(EDT 18:00/EST 17:00)라
    "거래일 == 오늘 + 마감 후"에 해당하고, KST 장중 실행은 ET로 전날 밤이라 "거래일 < 오늘"이
    되어 이미 완결된 거래일을 쓴다. 두 경우 모두 값이 같으므로 덮어써도 무해하다.
    """
    if not trade_date:
        return False
    now_et = (now or datetime.now(timezone.utc)).astimezone(_ET)
    today = now_et.date().isoformat()
    if today > trade_date:
        return True
    return today == trade_date and now_et.time() >= _US_CLOSE


def _prune(market_dir: Path) -> int:
    """보존 상한을 넘긴 오래된 파일 삭제. 파일명이 YYYY-MM-DD라 사전순 = 시간순이다."""
    files = sorted(market_dir.glob("*.json"))
    stale = files[:-KEEP_FILES] if len(files) > KEEP_FILES else []
    for f in stale:
        f.unlink()
    return len(stale)


def record(market: str, rows: list[dict] | None, trade_date: str | None) -> Path | None:
    """한 시장의 거래일 스냅샷을 기록하고 경로를 돌려준다. 기록하지 않았으면 None.

    rows가 없으면(수집 실패) 빈 파일·0행 파일을 만들지 않는다 — 결측 문법. "그날은 데이터가
    없었다"와 "그날은 거래가 없었다"를 파일 존재 여부로 구분할 수 있어야 한다.
    """
    if not rows or not trade_date:
        return None

    market_dir = HISTORY_DIR / market
    path = market_dir / f"{trade_date}.json"
    body = {
        "trade_date": trade_date,
        "market": market,
        "as_of_iso": datetime.now(timezone.utc).isoformat(),
        "population": len(rows),
        "rows": _shrink(rows),
    }
    save_json(path, body, compact=True)

    pruned = _prune(market_dir)
    log.info("히스토리 기록 %s %s (%d행 중 %d행 보존, 정리 %d)",
             market, trade_date, len(rows), len(body["rows"]), pruned)
    return path


def load(market: str, trade_date: str) -> dict | None:
    """단일 거래일 원장. Phase C(순위 변화·급증)의 읽기 진입점."""
    from utils.jsonio import load_json

    return load_json(HISTORY_DIR / market / f"{trade_date}.json", default=None)


def available_dates(market: str) -> list[str]:
    """보유한 거래일 목록(오름차순). Phase C가 윈도를 잡을 때 쓴다."""
    market_dir = HISTORY_DIR / market
    if not market_dir.is_dir():
        return []
    return sorted(p.stem for p in market_dir.glob("*.json"))
