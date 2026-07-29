"""Macroeconomics 생성 → docs/macro/index.html + docs/data/macro/{indicators,calendar}.json.

design/02, design/20 Phase 6(독립 트랙 — 시세 유니버스에 의존하지 않음). FRED/ECOS는 API 키
미설정 시 collectors가 사실대로 None을 반환하고, 화면은 결측을 카드 생략으로 이어간다
(추정·가짜 데이터 금지 원칙 계승).

design/25 Phase B: 수집·검증·발행은 전부 pipelines.get_macro()가 한다 — 이 모듈은 렌더만 한다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from repositories import macro_repository
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    ctx = {
        "root": "..",
        "nav": nav.context(active="macro"),
        "generated_at": fmt_kst(now_kst()) + " KST",
        "freshness": macro_repository.freshness_attrs(),
        "chart_window": macro_repository.STRIP_CHART_WINDOW_LABEL,
        **pipelines.get_macro(),
    }
    return render("pages/macro.html", ctx, DOCS_DIR / "macro" / "index.html")
