"""심볼별 일봉 종가 이력 수집(Yahoo Finance) — 미니차트 재료. raw만 반환(계산·렌더는 상위 계층).

design/25: Macro 페이지의 "금융시장" 스트립이 스파크라인을 그리려면 스팟 시세(market_collector)
외에 짧은 이력이 필요하다. market_collector와 **분리된 모듈**로 두는 이유는 책임이 다르기
때문이다 — 저쪽은 "지금 값", 이쪽은 "최근 궤적"이고 실패 시 파급도 다르다(이력이 없어도 스팟
타일은 그대로 보여야 한다).

yfinance 미설치 환경(데스크톱 32비트 키움 venv)에서는 조용히 None을 돌려준다 — market_collector와
동일 원칙이며, 이력은 GitHub Actions(64비트)가 채운다.
"""
from __future__ import annotations

import importlib.util

from utils.logging import get_logger

log = get_logger("collectors.history")

_memo: dict[str, list[float]] | None = None
_yf_available: bool | None = None


def _yahoo_available() -> bool:
    global _yf_available
    if _yf_available is None:
        _yf_available = importlib.util.find_spec("yfinance") is not None
    return _yf_available


def enabled() -> bool:
    return _yahoo_available()


def collect(symbols: dict[str, str], period: str = "3mo") -> dict[str, list[float]]:
    """{키: Yahoo 심볼} → {키: [종가 오름차순]}. 실패한 심볼은 **키 자체를 생략**한다.

    실행당 1회만 다운로드(메모이즈) — 같은 빌드에서 여러 생성기가 불러도 네트워크는 한 번이다.
    """
    global _memo
    if _memo is not None:
        return _memo
    if not _yahoo_available():
        log.info("yfinance 미설치 — 이력 수집 skipped(미니차트 생략)")
        _memo = {}
        return _memo

    out: dict[str, list[float]] = {}
    try:
        import yfinance as yf

        # 배치 다운로드(심볼당 왕복 대신 1회) — 일부 심볼이 실패해도 나머지는 채워진다.
        data = yf.download(
            list(symbols.values()), period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
    except Exception as exc:  # noqa: BLE001 - 이력 실패가 페이지 발행을 막지 않는다
        log.warning("이력 배치 수집 실패: %s", exc)
        _memo = {}
        return _memo

    for key, symbol in symbols.items():
        try:
            frame = data[symbol] if symbol in getattr(data, "columns", []) or (
                hasattr(data.columns, "levels") and symbol in data.columns.levels[0]
            ) else None
            if frame is None:
                continue
            closes = [float(v) for v in frame["Close"].dropna().tolist()]
            if len(closes) >= 2:
                out[key] = closes
        except Exception as exc:  # noqa: BLE001 - 심볼 하나의 실패는 그 심볼만 결측
            log.warning("이력 파싱 실패(%s/%s): %s", key, symbol, exc)

    log.info("이력 수집 완료: %d/%d 심볼", len(out), len(symbols))
    _memo = out
    return _memo
