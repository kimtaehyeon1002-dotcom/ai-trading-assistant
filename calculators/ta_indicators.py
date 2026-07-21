"""기술 지표 순수 계산(RSI/이평 이격/추세 판정) — 입력은 검증된 종가 시계열(오름차순, 계산 로직 없음)."""
from __future__ import annotations


def sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def deviation_pct(close: float, ma: float | None) -> float | None:
    if not ma:
        return None
    return round((close / ma - 1) * 100, 2)


def rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder's RSI — 표준 평활화. 최소 period+1개 종가 필요, 부족하면 None."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def rsi_label(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 70:
        return "과매수"
    if value <= 30:
        return "과매도"
    return "중립"


def trend_label(closes: list[float], lookback: int = 60) -> str | None:
    """lookback일 전 종가 대비 현재 종가 변화율로 추세를 판정한다(±2%p 밖이면 방향, 안이면 횡보)."""
    if len(closes) <= lookback:
        return None
    ref = closes[-lookback - 1]
    if not ref:
        return None
    change = (closes[-1] / ref - 1) * 100
    if change >= 2:
        return "상승 유지"
    if change <= -2:
        return "하락 유지"
    return "횡보"
