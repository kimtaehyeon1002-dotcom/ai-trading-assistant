"""Financial Statements 생성 → docs/financials/index.html (종목별 카드 발행은 파이프라인이 담당).

design/06, design/20 Phase 7. design/21 §159(업종 평균 무료 소스 부재)에 맞춰 자사 5년 단독
판정으로 축소하고, 설계 원안 15장 카드도 그룹당 대표 지표 1개(5장)로 1차 축소했다 — 실제로
검증 가능한 무료 데이터만으로 정직하게 시작한다.

가격은 이미 발행된 Stock Hub JSON의 종가를 재사용하므로 이 타깃은 "stock" 이후 실행돼야
PER이 채워진다(선행 조건, 없으면 PER만 결측).

design/25 Phase B: 수집·검증·발행은 pipelines.get_financials()로 이동했다 — 이 모듈은 렌더만 한다.
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from utils.dates import fmt_kst, now_kst


def generate() -> Path:
    out = DOCS_DIR / "financials" / "index.html"
    return render(
        "pages/financials.html",
        {
            "root": "..",
            "nav": nav.context(active="financials"),
            "generated_at": fmt_kst(now_kst()) + " KST",
            "universe": pipelines.get_financials()["universe"],
        },
        out,
    )
