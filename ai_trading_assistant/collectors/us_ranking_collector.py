"""S&P500 배치 랭킹 후보 수집 — FDR 구성종목 목록 + yfinance 배치 시세(design/21 §8, §225).

미국은 전종목 무료 스냅샷이 없어(design/21 §225 "미국 전시장 TOP30 무료 불가") S&P500
구성종목(config/universe.US_CANDIDATE_LISTING)을 랭킹 후보 유니버스로 채택한다. 배치 다운로드
1회로 전 종목 시세를 받아 종목당 재조회를 피한다(503종목 실측 약 23초 — 2026-07-21 실측).
실패 시 None(추정 금지). 실행당 1회만 다운로드(메모이즈).
"""
from __future__ import annotations

from config.universe import US_CANDIDATE_LISTING
from utils.logging import get_logger

log = get_logger("collectors.us_ranking")

_memo: list[dict] | None = None
_memo_done = False

# FDR가 클래스 주식 심볼의 점(.)을 생략해 반환한다(예: "BRK.B" → "BRKB"). Yahoo는 대시 형식만
# 인식하므로 교정한다(2026-07-21 실측: "BRKB"/"BFB"는 Yahoo 조회 실패, "BRK-B"/"BF-B"가 정상).
_YAHOO_TICKER_FIXES: dict[str, str] = {"BRKB": "BRK-B", "BFB": "BF-B"}


def _yahoo_symbol(raw: str) -> str:
    return _YAHOO_TICKER_FIXES.get(raw, raw).replace(".", "-")


def collect() -> list[dict] | None:
    """[{code, name, close, change_pct, volume, amount}] | None(수집 실패). code=Yahoo 심볼."""
    global _memo, _memo_done
    if _memo_done:
        return _memo
    _memo_done = True

    try:
        import FinanceDataReader as fdr
        import yfinance as yf

        listing = fdr.StockListing(US_CANDIDATE_LISTING)
        names = dict(zip(listing["Symbol"].astype(str), listing["Name"].astype(str)))
        symbols = [_yahoo_symbol(s) for s in names]
        df = yf.download(tickers=symbols, period="2d", group_by="ticker", threads=True, progress=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("US 랭킹 수집 실패: %s", exc)
        _memo = None
        return None

    rows: list[dict] = []
    for raw, symbol in zip(names, symbols):
        try:
            closes = df[symbol]["Close"].dropna()
            vols = df[symbol]["Volume"].dropna()
            if len(closes) < 1 or len(vols) < 1:
                continue
            close = float(closes.iloc[-1])
            volume = int(vols.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
            change_pct = round((close / prev - 1) * 100, 2) if prev else None
            rows.append({
                "code": symbol,
                "name": names[raw],
                "market": "US",
                "close": close,
                "change_pct": change_pct,
                "volume": volume,
                "amount": close * volume,
                "marcap": None,  # 배치 다운로드는 발행주식수를 제공하지 않아 시총 산출 불가(정직한 결측)
            })
        except Exception:  # noqa: BLE001 - 종목 단위 스킵
            continue
    _memo = rows or None
    return _memo


def collect_quotes(symbols: list[str]) -> dict[str, dict]:
    """임의 심볼 배치 시세(design/20 Phase 7 Hub) — S&P500 후보 밖 테마·watchlist 종목(예: TSM,
    NVO — 외국 민간발행사라 S&P500 미편입) 결측 보완용. 실패해도 예외 없이 빈 dict(결측 문법)."""
    if not symbols:
        return {}
    try:
        import yfinance as yf

        df = yf.download(tickers=symbols, period="2d", group_by="ticker", threads=True, progress=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("US 보조 시세 수집 실패: %s", exc)
        return {}

    out: dict[str, dict] = {}
    for symbol in symbols:
        try:
            closes = df[symbol]["Close"].dropna()
            vols = df[symbol]["Volume"].dropna()
            if len(closes) < 1:
                continue
            close = float(closes.iloc[-1])
            volume = int(vols.iloc[-1]) if len(vols) >= 1 else None
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
            change_pct = round((close / prev - 1) * 100, 2) if prev else None
            out[symbol] = {
                "close": close, "change_pct": change_pct, "volume": volume,
                "amount": (close * volume) if volume else close,
            }
        except Exception:  # noqa: BLE001 - 심볼 단위 스킵
            continue
    return out
