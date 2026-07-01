"""횡단면 정규화·스타일 가중·랭크 — 순수 함수, stdlib만. 설계서 §2.7.

각 신호를 시장 내 횡단면 z-score(winsorize)로 정규화 → 스타일 가중합 → percentile(0~100)+랭크.
가중치는 weights_version으로 버전 관리(재현성). 점수는 '관찰 지표'(추천 아님).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.analytics.theme_scoring.signals import ThemeRaw

WEIGHTS_VERSION = "v1-2026-06"

# 스타일 프리셋(price/volume/attention/news) — 합=1.0
STYLE_WEIGHTS: dict[str, dict[str, float]] = {
    "scalping": {"price": 0.25, "volume": 0.30, "attention": 0.15, "news": 0.30},
    "swing": {"price": 0.35, "volume": 0.25, "attention": 0.20, "news": 0.20},
    "long": {"price": 0.40, "volume": 0.15, "attention": 0.30, "news": 0.15},
}

_SIGNALS = ("price", "volume", "attention", "news")


@dataclass
class ThemeScoreResult:
    key: str  # theme 식별(slug 또는 id)
    score: float  # 0~100 (percentile 기반)
    rank: int  # 1=최상위
    percentile: float  # 0~100
    composite_z: float
    components: dict[str, float] = field(default_factory=dict)  # 신호별 z
    raw: dict[str, float] = field(default_factory=dict)  # 신호별 원값
    missing: list[str] = field(default_factory=list)
    weights_version: str = WEIGHTS_VERSION


def winsorize(values: list[float], p: float = 0.05) -> list[float]:
    """양 꼬리 p비율(개수 floor)을 분위값으로 클램프. 작은 N(p*n<1)이면 클램프 없음."""
    if not values:
        return []
    s = sorted(values)
    n = len(s)
    kcut = int(p * n)  # floor: 작은 N이면 0 → 무클램프
    lo = s[kcut]
    hi = s[n - 1 - kcut]
    return [min(max(v, lo), hi) for v in values]


def zscore(values: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    if std == 0:
        return [0.0 for _ in values]
    return [(v - mean) / std for v in values]


def robust_zscore(values: list[float], p: float = 0.05) -> list[float]:
    """winsorize로 **스케일(mean/std)만** 강건하게 구하고 z변환은 원본에 적용.

    → 이상치가 std를 부풀려 다른 테마를 압축하는 것은 막으면서, 최상위(부상) 테마의 순위는 보존.
    """
    n = len(values)
    if n == 0:
        return []
    w = winsorize(values, p)
    mean = sum(w) / n
    var = sum((v - mean) ** 2 for v in w) / n
    std = math.sqrt(var)
    if std == 0:
        return [0.0 for _ in values]
    return [(v - mean) / std for v in values]


def _percentiles(values: list[float]) -> list[float]:
    """동점 평균 순위 기반 percentile(0~100)."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0  # 0-based 평균 순위
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return [r / (n - 1) * 100.0 for r in ranks]


def composite_scores(
    raw_by_key: dict[str, ThemeRaw], *, style: str = "swing"
) -> list[ThemeScoreResult]:
    """테마별 raw 신호 → 횡단면 정규화·가중·랭크. style 없으면 swing 가중."""
    keys = list(raw_by_key.keys())
    if not keys:
        return []
    weights = STYLE_WEIGHTS.get(style, STYLE_WEIGHTS["swing"])

    # 신호별 강건 z-score(횡단면) — winsorize로 스케일만, 변환은 원본(순위 보존)
    z_by_signal: dict[str, list[float]] = {}
    for sig in _SIGNALS:
        col = [getattr(raw_by_key[k], sig) for k in keys]
        z_by_signal[sig] = robust_zscore(col)

    # 가중 합성 z
    composites: list[float] = []
    for idx in range(len(keys)):
        comp = sum(weights[sig] * z_by_signal[sig][idx] for sig in _SIGNALS)
        composites.append(comp)

    pct = _percentiles(composites)
    order = sorted(range(len(keys)), key=lambda i: composites[i], reverse=True)
    rank_of = {idx: r + 1 for r, idx in enumerate(order)}

    results: list[ThemeScoreResult] = []
    for idx, key in enumerate(keys):
        rr = raw_by_key[key]
        results.append(
            ThemeScoreResult(
                key=key,
                score=round(pct[idx], 2),
                rank=rank_of[idx],
                percentile=round(pct[idx], 2),
                composite_z=round(composites[idx], 4),
                components={sig: round(z_by_signal[sig][idx], 4) for sig in _SIGNALS},
                raw={sig: round(getattr(rr, sig), 6) for sig in _SIGNALS},
                missing=list(rr.missing),
                weights_version=WEIGHTS_VERSION,
            )
        )
    results.sort(key=lambda r: r.rank)
    return results
