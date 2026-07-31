"""야간선물 시세 — KRX 야간파생시장(2025-06 개설, 18:00~익일 05:00).

2025-06 EUREX 연계 종료 후, 야간장은 **주간과 동일한 KRX 종목**을 연장 시간대에 거래한다.
따라서 별도 '야간' 종목코드는 없다. 최근월(front-month) 코스피200/코스닥150 선물을
야간 시간대에 조회하면 그 값이 곧 야간선물 시세다.

종목코드는 하드코딩하지 않고 로그인 세션의 GetFutureList에서 종목명 패턴으로 최근월을
자동 선택한다(월물이 롤오버되어도 안전). 시세는 opt50001(선물시세) 단일 레코드.
"""
from __future__ import annotations

import re

from collectors.kiwoom_desktop.api import KiwoomAPI, fix_mojibake
from config.calendar import (
    KR_FUTURES_REGULAR_CLOSE,
    KR_NIGHT_CLOSE,
    KR_NIGHT_OPEN,
    is_kr_futures_close_window,
    is_kr_night_session,
)
from config.markets import BASE_DAY_CLOSE, BASE_PREV_CLOSE
from utils.dates import now_kst
from utils.logging import get_logger

log = get_logger("collectors.kiwoom_futures")

TR_CODE = "opt50001"
RQ_NAME = "opt50001_quote"

# 실계좌 검증(2026-07-06 / 2026-07-31 재확인): opt50001의 기준가는 야간세션 중에도 **직전
# 정규장의 전일 종가**에 머문다 — 즉 방금 끝난 정규장 종가로 롤오버되지 않는다. 그래서 이
# 기준가로 계산한 등락률에는 당일 주간 변동이 통째로 섞인다(2026-07-30 야간 -3.46% 중
# -1.2%p가 그날 주간 하락분이었다).
#   재확인 근거(sync_auto.log 원본 필드 + 현물 종가 대조, 기준가/현물 비율):
#     07-28 22:30 기준가 1074.50 / KOSPI 07-27 종가 = 0.15905
#     07-29 22:34 기준가  956.75 / KOSPI 07-28 종가 = 0.15884
#     07-31 00:01 기준가  898.65 / KOSPI 07-29 종가 = 0.15868   ← 07-30 종가가 아니다
# 따라서 '밤사이 변동'을 얻으려면 당일 정규장 종가를 **따로 수집해** 기준으로 삼아야 한다
# (opt50001엔 주간 종가 필드가 없다 — 정산가·전일비는 실측에서 항상 빈 값이었다).
# 그 수집 창이 config.calendar.is_kr_futures_close_window(15:45~18:00)이며, 확보 실패 시에만
# 기준가 폴백(BASE_PREV_CLOSE)으로 내려가고 그 사실을 값에 붙여 표시단까지 전달한다.
# Kiwoom 제공 '등락율'은 기준이 애매해 그대로 믿지 않고 항상 직접 계산한다(폴백만 등락율).
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "price": ("현재가",),
    "base": ("기준가", "기준가격", "정산가"),  # 전일 정규장 종가(등락 기준가)
    "change_pct": ("등락률", "등락율"),          # 기준가 미제공 시 폴백
}
_ALL_FIELDS = [f for cands in _FIELD_CANDIDATES.values() for f in cands]

# 종목명 패턴 → 최근월 선택. 코스피200 선물명은 접두어 없이 'F YYYYMM',
# 코스닥150은 '코스닥 F YYYYMM'(코스닥글로벌 등 섹터물 제외).
_FRONT_MONTH_PATTERNS: dict[str, re.Pattern] = {
    "kospi_night": re.compile(r"^F\s+(\d{6})$"),
    "kosdaq_night": re.compile(r"^코스닥\s+F\s+(\d{6})$"),
}


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return None


def _list_codes(api: KiwoomAPI) -> list[str]:
    """선물 종목코드 리스트 — 버전별로 함수명이 달라 여러 개 시도."""
    codes: list[str] = []
    for call in ("GetFutureList()", "GetActPriceList()"):
        try:
            raw = api.ocx.dynamicCall(call) or ""
        except Exception:  # noqa: BLE001 - 미지원 함수는 건너뜀
            continue
        codes += [c for c in str(raw).replace(",", ";").split(";") if c.strip()]
    seen: set[str] = set()
    return [c for c in codes if not (c in seen or seen.add(c))]


def _name_of(api: KiwoomAPI, code: str) -> str:
    return fix_mojibake((api.ocx.dynamicCall("GetMasterCodeName(QString)", code) or "").strip())


def _family(name: str) -> str:
    """월물/스프레드 표기를 떼어낸 상품군 이름(진단 덤프용)."""
    return re.split(r"\s*(?:F|SP)\s*\d", name)[0].strip() or name


def discover_front_month(api: KiwoomAPI) -> dict[str, str]:
    """{'kospi_night': code, 'kosdaq_night': code} — 최근월 지수선물 코드.

    패턴 매칭 실패 시 상품군 단위 진단 덤프를 남긴다.
    """
    pairs = [(c, _name_of(api, c)) for c in _list_codes(api)]
    out: dict[str, str] = {}
    for key, pat in _FRONT_MONTH_PATTERNS.items():
        matches = [(m.group(1), c, n) for c, n in pairs if (m := pat.match(n))]
        if matches:
            month, code, name = min(matches)  # 최근월(가장 작은 YYYYMM)
            out[key] = code
            log.info("%s 최근월: %s (%s)", key, code, name)

    if len(out) < len(_FRONT_MONTH_PATTERNS):
        fams: dict[str, str] = {}
        for c, n in pairs:
            fams.setdefault(_family(n), n)
        log.warning("일부 지수선물 미발견(found=%s) — 상품군 %d개 덤프:", list(out), len(fams))
        for fam, sample in sorted(fams.items()):
            log.warning("  [%s] 예: %s", fam, sample)
    return out


def fetch_quote(api: KiwoomAPI, code: str) -> dict | None:
    """opt50001 단일 시세 → {'price', 'change_pct', 'ref_price', 'base_kind'} | None.

    여기서 계산하는 등락률은 항상 Kiwoom 기준가(=직전 정규장의 **전일** 종가) 대비이므로
    base_kind는 BASE_PREV_CLOSE다. 야간 시세를 '밤사이 변동'으로 바꾸는 환산은 당일 정규장
    종가를 아는 호출부가 rebase_to_day_close()로 수행한다.
    마감·개장전엔 현재가=기준가라 등락률이 0.0이 되며, 이는 상위(sync/validator)에서
    '유효 시세 아님'으로 걸러 직전 값을 유지한다.
    """
    api.set_input("종목코드", code)
    meta = api.comm_rq(RQ_NAME, TR_CODE, fields=_ALL_FIELDS)
    rows = meta.get("rows", [])
    if not rows:
        return None
    raw = rows[0]
    log.info("선물 시세 raw(필드 검증용) %s: %s", code, raw)
    price = next((_num(raw[f]) for f in _FIELD_CANDIDATES["price"] if raw.get(f)), None)
    base = next((_num(raw[f]) for f in _FIELD_CANDIDATES["base"] if raw.get(f)), None)
    kw_chg = next((_num(raw[f]) for f in _FIELD_CANDIDATES["change_pct"] if raw.get(f)), None)
    if price is None:
        return None
    price = abs(price)  # Kiwoom은 하락 시 현재가에 '-' 부호(가격은 양수로 정규화)
    if not price:
        return None
    ref = abs(base) if base and abs(base) > 0 else None
    change_pct = round((price / ref - 1) * 100, 2) if ref else kw_chg
    log.info("선물 등락 %s: price=%s base=%s → chg=%s%% (kiwoom등락률=%s)",
             code, price, ref, change_pct, kw_chg)
    return {"price": price, "change_pct": change_pct,
            "ref_price": ref, "base_kind": BASE_PREV_CLOSE}


def fetch_front_month_quotes(api: KiwoomAPI) -> dict[str, dict | None]:
    """최근월 지수선물 2종 일괄 조회 — 창(야간/마감)에 관계없이 '지금 시세'를 그대로 돌려준다.

    무엇으로 해석할지(야간 시세인가, 당일 정규장 종가인가)는 호출 시각이 결정하므로
    창 판정은 호출부(app.sync)가 한다.
    """
    codes = discover_front_month(api)
    return {
        "kospi_night": fetch_quote(api, codes["kospi_night"]) if codes.get("kospi_night") else None,
        "kosdaq_night": fetch_quote(api, codes["kosdaq_night"]) if codes.get("kosdaq_night") else None,
    }


def rebase_to_day_close(leg: dict, day_close: float | None) -> dict:
    """야간 시세를 '직전 정규장 종가 대비'로 환산 — 당일 주간 변동분을 걷어낸다.

    day_close가 없거나 비정상이면 원본(기준가 대비)을 그대로 돌려준다. 값을 지어내지 않고
    base_kind로 '어느 기준인지'를 정직하게 남기는 것이 폴백의 계약이다.
    """
    price = leg.get("price")
    if not day_close or day_close <= 0 or not price:
        return leg
    return {**leg,
            "change_pct": round((price / day_close - 1) * 100, 2),
            "ref_price": day_close,
            "base_kind": BASE_DAY_CLOSE}


def night_session_state() -> tuple[bool, str]:
    """(세션 중인가, 사람이 읽는 상태 문구) — 수집 시도 전 세션 창 판정(design/23 P2).

    창 밖(05:00~18:00)에 조회하면 opt50001은 현재가=기준가인 flat 스냅샷을 돌려주고,
    그것은 '야간 시세가 없는 것'이지 '변동이 0인 것'이 아니다. 두 경우가 로그에서 구분되지
    않아 원인 파악이 늦어졌으므로, 세션 창을 먼저 판정해 사유를 분리해 기록한다.
    """
    now = now_kst()
    if is_kr_night_session(now):
        return True, f"야간 세션 중({KR_NIGHT_OPEN}~{KR_NIGHT_CLOSE} KST, 현재 {now:%H:%M})"
    return False, (f"야간 세션 아님(창 {KR_NIGHT_OPEN}~{KR_NIGHT_CLOSE} KST, 현재 {now:%H:%M}) "
                   f"— 조회해도 마감 스냅샷만 나온다")


def close_window_state() -> tuple[bool, str]:
    """(정규장 종가 확정 창인가, 사람이 읽는 상태 문구).

    이 창(15:45~18:00)에서 받은 현재가가 곧 당일 정규장 종가이고, 그것이 그날 밤 등락률의
    기준가가 된다. 창을 놓치면 그 밤은 기준가 폴백으로 내려간다(값이 사라지진 않는다).
    """
    now = now_kst()
    if is_kr_futures_close_window(now):
        return True, (f"정규장 종가 확정 창({KR_FUTURES_REGULAR_CLOSE}~{KR_NIGHT_OPEN} KST, "
                      f"현재 {now:%H:%M})")
    return False, (f"종가 확정 창 아님(창 {KR_FUTURES_REGULAR_CLOSE}~{KR_NIGHT_OPEN} KST, "
                   f"현재 {now:%H:%M})")
