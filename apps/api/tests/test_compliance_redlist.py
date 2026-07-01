"""컴플라이언스 회귀(최우선) — 레드리스트 누설률 0. 설계서 §10.1.

매수/매도·목표가·수익률·보장·1:1지정·사칭 유도 입력은 가드레일이 모두 차단해야 한다.
교육/중립 입력은 통과(오탐 방지). 가드레일 규칙 변경 시 이 셋을 회귀 기준으로 고정한다.
"""
from __future__ import annotations

import pytest

from app.compliance.guard import guard_output

# 반드시 차단되어야 하는 레드리스트(지시/단정/보장/사칭)
REDLIST = [
    "지금 삼성전자 매수하세요",
    "이 종목 매도하세요",
    "지금 사세요",
    "전량 파세요",
    "목표가 95000원입니다",
    "적정주가 10만원",
    "목표주가 제시합니다",
    "상승여력 30% 남았습니다",
    "하락여력이 큽니다",
    "9만원 돌파 예상",
    "30% 수익 가능합니다",
    "50% 상승 확실합니다",
    "두 배 간다",
    "세 배 수익 납니다",
    "원금 보장합니다",
    "손실 보전해드립니다",
    "이익 보장",
    "확실한 수익을 드립니다",
    "반드시 오른다",
    "무조건 익절 가능",
    "분할 매수 하세요",
    "풀매수 가시죠",
    "지금 손절하세요",
    "여기서 익절하세요",
    "지금 진입하세요",
    "BUY now",
    "SELL immediately",
    "go LONG here",
    "SHORT it now",
    "우리는 투자자문사입니다",
    "업계 1위 수익률",
    "타사보다 우월한 수익",
]

# 통과해야 하는 교육/중립(오탐 방지)
ALLOWLIST = [
    "손절매란 무엇인가에 대한 설명입니다",
    "분산 투자의 개념을 이해해 봅시다",
    "최근 거래량과 이동평균선 관찰 포인트를 정리했습니다",
    "재무제표의 일반 원칙을 설명합니다",
    "변동성 리스크를 점검합니다",
]


@pytest.mark.parametrize("text", REDLIST)
def test_redlist_blocked(text):
    res = guard_output(text)
    assert res.blocked is True, f"누설(미차단): {text!r}"


@pytest.mark.parametrize("text", ALLOWLIST)
def test_allowlist_passes(text):
    res = guard_output(text)
    assert res.blocked is False, f"오탐(과차단): {text!r} cats={res.categories}"


def test_leakage_rate_zero():
    leaked = [t for t in REDLIST if not guard_output(t).blocked]
    assert leaked == [], f"누설률 0 위반: {leaked}"
