"""규칙 1차 필터 — 매수/매도·목표가·수익률·보장·사칭 탐지. 설계서 §2.6 B-2.

오탐 방지: 교육 문맥("손절매란")은 허용하고 지시형 어미와 결합될 때만 차단하도록 패턴 설계.
2차 LLM 분류기(Haiku)는 Phase 2에서 classifier.py로 추가(의미 기반 우회 탐지).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (category, pattern) — 지시형/단정형 결합 위주
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("buy_sell", re.compile(r"(매수|매도|사세요|파세요|매수하|매도하|분할\s*매수|풀\s*매수|손절하|익절하|진입하)")),
    ("buy_sell", re.compile(r"\b(BUY|SELL|LONG|SHORT)\b", re.IGNORECASE)),
    ("target_price", re.compile(r"(목표\s*가|적정\s*주가|목표\s*주가|상승\s*여력|하락\s*여력)")),
    ("target_price", re.compile(r"\d+\s*만?\s*원\s*(돌파|목표|예상)")),
    ("return_promise", re.compile(r"\d+\s*%\s*(수익|상승|수익률)|\bN?\s*배\s*(수익|상승)|두\s*배")),
    ("guarantee", re.compile(r"(원금\s*보장|손실\s*보전|이익\s*보장|확실(한)?\s*수익|반드시\s*오른|무조건)")),
    ("impersonation", re.compile(r"(투자자문(사|업자)|업계\s*1위|타사보다\s*우월)")),
]

# 교육 문맥 화이트리스트(차단 예외)
_EDU_WHITELIST = re.compile(r"(란\s*무엇|의\s*개념|이란|를\s*이해|에\s*대한\s*설명|일반\s*원칙)")


@dataclass
class RuleHit:
    category: str
    span: str


def scan(text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for category, pat in _PATTERNS:
        for m in pat.finditer(text):
            window = text[max(0, m.start() - 12) : m.end() + 12]
            if _EDU_WHITELIST.search(window):
                continue
            hits.append(RuleHit(category=category, span=m.group(0)))
    return hits
