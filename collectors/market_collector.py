"""시장 데이터 수집 — Yahoo(지수/WTI/환율폴백) + Frankfurter/ExchangeRate-API(USD/KRW).

반환은 raw dict(모델 변환은 repositories/). 실패 항목은 None(추정 금지).
실행당 1회만 다운로드(메모이즈).

yfinance 미설치 환경(데스크톱 32비트 키움 venv)에서는 CI가 커밋해 둔 마지막 시세
(data/cache/market_last.json)를 재사용한다 — 각 항목에 원 수집 시각(as_of)이 찍혀 있어
freshness 배지가 나이를 정직하게 표시한다(추정이 아니라 시점 명시된 사실 데이터).
데스크톱 빌드가 대시보드를 '데이터 없음'으로 덮어쓰는 문제의 근본 해결(kiwoom_night.json의
데스크톱→CI 전달과 대칭 구조, 방향만 반대).
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone

from config.markets import (
    CROSS_CHECK_CODES,
    CROSS_CHECK_TOLERANCE_PP,
    EXTENDED_SYMBOLS,
    MORNING_US_INDICES,
    WTI_SYMBOL,
)
from config.settings import DATA_CACHE_DIR
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("collectors.market")

# CI(yfinance 가용)→데스크톱 전달 캐시. 정상 시 news cron(30분)마다 갱신되므로 나이 ≤0.5h;
# 상한은 CI 장애·주말 정지 대비 여유치다(이보다 낡으면 빈 타일이 낫다 — 팩트 우선).
_LAST_CACHE = DATA_CACHE_DIR / "market_last.json"
MARKET_LAST_MAX_AGE_H = 26

_memo: dict | None = None
_yf_available: bool | None = None
_fdr_ok: bool | None = None


def _yahoo_available() -> bool:
    """yfinance 설치 여부(1회 판정). 데스크톱 32비트 키움 venv엔 없음(pandas 휠 부재로
    설치 불가) — Yahoo 시세는 GitHub Actions(64비트)가 담당한다. 여기선 조용히 스킵한다."""
    global _yf_available
    if _yf_available is None:
        _yf_available = importlib.util.find_spec("yfinance") is not None
    return _yf_available


# fast_info 키는 yfinance 버전에 따라 snake_case/camelCase가 갈린다. 실측(yfinance 1.5.1)에서는
# camelCase만 값이 있고 snake_case는 전부 None을 돌려준다 — 한쪽만 보면 전 심볼이 조용히
# 결측되므로 후보를 명시해 순서대로 찾는다(이 폴백은 장식이 아니라 필수다).
_PRICE_KEYS = ("lastPrice", "last_price")
_PREV_KEYS = ("previousClose", "previous_close", "regularMarketPreviousClose")


def _first(fi, keys: tuple[str, ...]) -> float | None:
    for k in keys:
        v = fi.get(k)
        if v is not None:
            return float(v)
    return None


def _yahoo(symbol: str) -> tuple[float | None, float | None, float | None]:
    """(가격, 전일대비%, 전일종가) — 실패는 (None, None, None).

    yfinance 미설치면 심볼마다 경고를 찍지 않고 조용히 스킵한다(설치돼 있는데 호출이
    실패한 경우만 경고 — 진짜 오류이므로)."""
    if not _yahoo_available():
        return None, None, None
    try:
        import yfinance as yf

        fi = yf.Ticker(symbol).fast_info
        price = _first(fi, _PRICE_KEYS)
        prev = _first(fi, _PREV_KEYS)
        if price is None:
            return None, None, None
        pct = round((price / prev - 1) * 100, 2) if prev else None
        return price, pct, prev
    except Exception as exc:  # noqa: BLE001
        log.warning("yahoo 실패 %s: %s", symbol, exc)
        return None, None, None


def _fdr_available() -> bool:
    """FinanceDataReader(교차검증 소스) 설치 여부 — 32비트 키움 venv엔 없다(pandas 휠 부재)."""
    global _fdr_ok
    if _fdr_ok is None:
        _fdr_ok = importlib.util.find_spec("FinanceDataReader") is not None
    return _fdr_ok


def _fdr_quote(code: str) -> tuple[float | None, float | None]:
    """(최근 종가, 전일대비%) — FinanceDataReader 일봉 2개로 close-to-close 계산."""
    try:
        import FinanceDataReader as fdr

        closes = fdr.DataReader(code).get("Close")
        closes = closes.dropna() if closes is not None else None
        if closes is None or len(closes) < 2:
            return None, None
        last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
        return last, (round((last / prev - 1) * 100, 2) if prev else None)
    except Exception as exc:  # noqa: BLE001
        log.warning("fdr 실패 %s: %s", code, exc)
        return None, None


def _cross_check(out: dict[str, dict | None]) -> None:
    """Yahoo 값을 독립 소스와 대조해 quality를 부착한다(out을 제자리 수정).

    verified   — 두 소스 등락률이 허용오차 이내(값을 믿을 근거가 생김)
    degraded   — 어긋남. 값은 남기되 표시단이 경고할 수 있게 표시한다(임의로 어느 쪽이 옳다고
                 판정하지 않는다 — 둘 중 무엇이 맞는지는 여기서 알 수 없다)
    unverified — 대조 소스가 없거나 대조 대상이 아님(종전과 동일한 신뢰수준)
    Yahoo가 결측이면 대조 소스 값으로 채운다(가짜가 아니라 실제 2차 소스 값이다).
    """
    if not _fdr_available():
        log.info("FinanceDataReader 미설치 — 교차검증 스킵(모든 값 unverified)")
        return
    for key, code in CROSS_CHECK_CODES.items():
        ref_price, ref_pct = _fdr_quote(code)
        entry = out.get(key)
        if entry is None:
            if ref_price is not None:
                out[key] = {"price": ref_price, "change_pct": ref_pct,
                            "source": "finance-datareader", "quality": "unverified"}
                log.info("%s Yahoo 결측 → 교차 소스(%s) 값 사용: %s (%s%%)",
                         key, code, ref_price, ref_pct)
            continue
        if ref_pct is None or entry.get("change_pct") is None:
            entry["quality"] = "unverified"
            continue
        gap = abs(entry["change_pct"] - ref_pct)
        if gap > CROSS_CHECK_TOLERANCE_PP:
            entry["quality"] = "degraded"
            log.warning("교차검증 불일치 %s: yahoo %.2f%% vs %s %.2f%% (차 %.2f%%p > %.1f%%p)",
                        key, entry["change_pct"], code, ref_pct, gap, CROSS_CHECK_TOLERANCE_PP)
        else:
            entry["quality"] = "verified"


def _entry(price: float, chg: float | None, prev: float | None, source: str) -> dict:
    """raw 항목 조립 — previous_close는 change_abs 산출 재료(repositories/에서 계산)."""
    e = {"price": price, "change_pct": chg, "source": source}
    if prev is not None:
        e["previous_close"] = prev
    return e


def _usdkrw() -> dict | None:
    import requests

    try:  # 1) Frankfurter(ECB)
        r = requests.get("https://api.frankfurter.app/latest",
                         params={"from": "USD", "to": "KRW"}, timeout=10)
        r.raise_for_status()
        return {"price": float(r.json()["rates"]["KRW"]), "change_pct": None,
                "source": "frankfurter(ECB)"}
    except Exception as exc:  # noqa: BLE001
        log.warning("frankfurter 실패: %s", exc)
    try:  # 2) ExchangeRate-API
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        return {"price": float(r.json()["rates"]["KRW"]), "change_pct": None,
                "source": "exchangerate-api"}
    except Exception as exc:  # noqa: BLE001
        log.warning("exchangerate-api 실패: %s", exc)
    price, chg, prev = _yahoo("USDKRW=X")  # 3) Yahoo
    return _entry(price, chg, prev, "yahoo") if price is not None else None


def _save_last(out: dict[str, dict | None]) -> None:
    """라이브 Yahoo 수집 결과를 커밋 캐시에 기록(CI에서 실행 — 워크플로가 data/를 커밋).

    usdkrw는 제외(항상 라이브 소스가 있음). 유효 항목이 하나도 없으면 기존 캐시를 덮지 않는다.
    """
    now = datetime.now(timezone.utc).isoformat()
    entries = {k: {**e, "as_of": now} for k, e in out.items()
               if k != "usdkrw" and isinstance(e, dict)}
    if not entries:
        return
    try:
        save_json(_LAST_CACHE, {"as_of": now, "entries": entries})
    except OSError as exc:
        log.warning("market_last.json 기록 실패(빌드는 계속): %s", exc)


def _load_last() -> dict[str, dict]:
    """커밋 캐시에서 마지막 Yahoo 시세를 읽는다 — 상한보다 낡았거나 없으면 {}(빈 타일 유지)."""
    data = load_json(_LAST_CACHE, default=None)
    if not isinstance(data, dict):
        return {}
    try:
        as_of = datetime.fromisoformat(data.get("as_of", ""))
    except ValueError:
        return {}
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - as_of
    if age > timedelta(hours=MARKET_LAST_MAX_AGE_H):
        log.warning("market_last.json 만료(%.1fh 경과, 상한 %dh) — 캐시 재사용 안 함",
                    age.total_seconds() / 3600, MARKET_LAST_MAX_AGE_H)
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def collect() -> dict[str, dict | None]:
    """모닝리포트 8지표 + 확장 유니버스(design/20 Phase 3) → raw {price, change_pct, source} | None."""
    global _memo
    if _memo is not None:
        return _memo

    live = _yahoo_available()
    cached: dict[str, dict] = {}
    if not live:
        cached = _load_last()
        log.info("yfinance 미설치 — Yahoo 라이브 수집 스킵, 커밋 캐시 재사용 %d항목(as_of는 "
                 "항목별 유지 → freshness 배지가 나이 표시). 환율은 라이브 수집.", len(cached))

    def _yahoo_or_cache(key: str, symbol: str) -> dict | None:
        if not live:
            return cached.get(key)
        price, chg, prev = _yahoo(symbol)
        return _entry(price, chg, prev, "yahoo") if price is not None else None

    out: dict[str, dict | None] = {"usdkrw": _usdkrw()}
    out["wti"] = _yahoo_or_cache("wti", WTI_SYMBOL)
    for key, symbol, _label in MORNING_US_INDICES:
        out[key] = _yahoo_or_cache(key, symbol)
    for key, symbol, _label in EXTENDED_SYMBOLS:
        out[key] = _yahoo_or_cache(key, symbol)

    if live:
        _cross_check(out)  # 캐시 재사용분은 이미 수집 당시 판정된 quality를 갖고 있다
        _save_last(out)

    _memo = out
    return out
