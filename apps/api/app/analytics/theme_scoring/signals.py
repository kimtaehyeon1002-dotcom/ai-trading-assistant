"""4신호 집계(테마 단위) — 순수 함수, stdlib만. 설계서 §2.7.

신호:
  ① 가격 상승률 — 구성종목 수익률 시총가중 평균의 **벤치마크 대비 초과수익**(멀티 호라이즌 블렌딩)
  ② 거래량 증가율 — RVOL(당일/과거평균) 시총가중
  ③ 시장 관심도 — breadth(상승 구성종목 비율) [+워치리스트/조회는 engine에서 가산 가능]
  ④ 뉴스 모멘텀 — 건수 '가속도'(최근창/기준창) 시총가중

결측은 중립(0)으로 처리하고 플래그를 남긴다. 정규화/가중/랭크는 scoring.py(횡단면).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 스타일별 호라이즌 블렌딩(단타=초단기, 스윙=균형, 장기=장기 가중)
HORIZON_BLEND: dict[str, dict[str, float]] = {
    "intraday": {"1d": 1.0},
    "swing": {"1d": 0.4, "5d": 0.6},
    "long": {"5d": 0.3, "20d": 0.7},
}


@dataclass
class Constituent:
    instrument_id: int
    mcap: float = 1.0  # 시총가중치(없으면 1.0=동일가중)
    ret: dict[str, float] = field(default_factory=dict)  # {"1d":.., "5d":.., "20d":..} 원수익률(%)
    vol: float | None = None  # 당일 거래량
    avg_vol: float | None = None  # 과거 평균 거래량(예: 20일 MA)
    news_recent: int = 0  # 최근창 뉴스 건수
    news_baseline: float = 0.0  # 기준창 평균 뉴스 건수


@dataclass
class ThemeRaw:
    price: float = 0.0
    volume: float = 0.0
    attention: float = 0.0
    news: float = 0.0
    missing: list[str] = field(default_factory=list)  # 결측 신호(중립 처리됨)
    n: int = 0


def _cap_weights(constituents: list[Constituent]) -> list[float]:
    total = sum(max(c.mcap, 0.0) for c in constituents)
    if total <= 0:
        n = len(constituents) or 1
        return [1.0 / n] * len(constituents)
    return [max(c.mcap, 0.0) / total for c in constituents]


def _blended_return(c: Constituent, blend: dict[str, float]) -> float | None:
    num = 0.0
    wsum = 0.0
    for h, w in blend.items():
        if h in c.ret and c.ret[h] is not None:
            num += w * c.ret[h]
            wsum += w
    if wsum == 0:
        return None
    return num / wsum


def _blended_bench(benchmark_ret: dict[str, float], blend: dict[str, float]) -> float:
    num = 0.0
    wsum = 0.0
    for h, w in blend.items():
        if h in benchmark_ret:
            num += w * benchmark_ret[h]
            wsum += w
    return num / wsum if wsum else 0.0


def theme_raw_signals(
    constituents: list[Constituent],
    *,
    benchmark_ret: dict[str, float] | None = None,
    timeframe: str = "swing",
) -> ThemeRaw:
    """구성종목 메트릭 → 테마 단위 raw 4신호(미정규화). 결측은 중립(0)+플래그."""
    raw = ThemeRaw(n=len(constituents))
    if not constituents:
        raw.missing = ["price", "volume", "attention", "news"]
        return raw

    blend = HORIZON_BLEND.get(timeframe, HORIZON_BLEND["swing"])
    bench = _blended_bench(benchmark_ret or {}, blend)
    w = _cap_weights(constituents)

    # ① 가격: 시총가중 초과수익
    price_num = 0.0
    price_w = 0.0
    up = 0
    counted = 0
    for wi, c in zip(w, constituents, strict=True):
        r = _blended_return(c, blend)
        if r is None:
            continue
        price_num += wi * (r - bench)
        price_w += wi
        counted += 1
        if r > bench:
            up += 1
    if price_w > 0:
        raw.price = price_num / price_w
    else:
        raw.missing.append("price")

    # ③ 관심도: breadth(초과수익 양수 비율)
    if counted > 0:
        raw.attention = up / counted
    else:
        raw.missing.append("attention")

    # ② 거래량: 시총가중 RVOL
    vol_num = 0.0
    vol_w = 0.0
    for wi, c in zip(w, constituents, strict=True):
        if c.vol is not None and c.avg_vol:
            vol_num += wi * (c.vol / c.avg_vol)
            vol_w += wi
    if vol_w > 0:
        raw.volume = vol_num / vol_w
    else:
        raw.missing.append("volume")

    # ④ 뉴스: 시총가중 모멘텀(가속도) — 기준창 0이면 중립
    news_num = 0.0
    news_w = 0.0
    for wi, c in zip(w, constituents, strict=True):
        if c.news_baseline > 0:
            news_num += wi * (c.news_recent / c.news_baseline)
            news_w += wi
    if news_w > 0:
        raw.news = news_num / news_w
    else:
        raw.missing.append("news")

    return raw
