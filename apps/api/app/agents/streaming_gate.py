"""스트리밍 지연 게이트 — 고위험 토큰을 문장 단위로 버퍼→검증→방출. 설계서 §2.6.

SSE에서 위반 토큰이 한 번 전송되면 회수 불가하다. 따라서 LLM 델타를 문장 경계까지
버퍼링하고, 규칙 스캔을 통과한 문장만 방출한다. 위반 문장은 중립 표지로 치환(미노출).

이 모듈은 stdlib + compliance.rules만 의존한다 → 네트워크/DB 없이 단위 테스트 가능.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.compliance.rules import scan

# 문장 경계: 마침표/물음표/느낌표/한국어 구두점 + 개행까지 포함해 한 조각으로 방출.
_BOUNDARY = re.compile(r"[^.!?。\n]*[.!?。\n]")

# 위반 문장 치환 표지(원문 미노출 + 사유 고지).
# 주의: 이 표지 자체가 규칙(rules.scan)에 걸리지 않도록 트리거 토큰(매수/매도·목표가·수익률 등)을
# 포함하지 않는다 — 최종 풀 검증(guard_output)에서 표지 때문에 전체가 차단되는 것을 방지.
REDACTED_NOTICE = "[컴플라이언스 검토에 따라 일부 문장은 표시하지 않았습니다.] "


@dataclass
class GateEmission:
    text: str  # 실제 방출 텍스트(위반 시 치환됨)
    redacted: bool = False
    categories: list[str] = field(default_factory=list)


class SentenceGate:
    """delta를 받아 완성된 문장만 검증 후 방출. 종료 시 flush()로 잔여 버퍼 처리."""

    def __init__(self) -> None:
        self._buf = ""
        self.redacted_count = 0
        self.categories: list[str] = []

    def feed(self, delta: str) -> list[GateEmission]:
        self._buf += delta
        out: list[GateEmission] = []
        while True:
            m = _BOUNDARY.match(self._buf)
            if not m:
                break
            sentence = m.group(0)
            self._buf = self._buf[m.end() :]
            out.append(self._check(sentence))
        return out

    def flush(self) -> list[GateEmission]:
        if not self._buf.strip():
            self._buf = ""
            return []
        sentence = self._buf
        self._buf = ""
        return [self._check(sentence)]

    def _check(self, sentence: str) -> GateEmission:
        hits = scan(sentence)
        if hits:
            cats = sorted({h.category for h in hits})
            self.redacted_count += 1
            for c in cats:
                if c not in self.categories:
                    self.categories.append(c)
            return GateEmission(text=REDACTED_NOTICE, redacted=True, categories=cats)
        return GateEmission(text=sentence)
