"""Theme Scoring Engine — 4신호(가격/거래량/관심도/뉴스) 종합 코드 계산. 설계서 §2.7.

LLM 비의존·결정적·재현 가능. 점수는 '강세 추천'이 아니라 **관찰 지표**(컴플라이언스 정합).
signals.py(신호 집계) → scoring.py(횡단면 정규화·가중·랭크) → engine.py(데이터 수집 오케스트레이션).
"""
from app.analytics.theme_scoring.scoring import (
    STYLE_WEIGHTS,
    WEIGHTS_VERSION,
    ThemeScoreResult,
    composite_scores,
)
from app.analytics.theme_scoring.signals import Constituent, ThemeRaw, theme_raw_signals

__all__ = [
    "Constituent",
    "ThemeRaw",
    "theme_raw_signals",
    "composite_scores",
    "ThemeScoreResult",
    "STYLE_WEIGHTS",
    "WEIGHTS_VERSION",
]
