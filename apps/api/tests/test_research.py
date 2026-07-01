"""Phase 2 AI Research — 오프라인 검증 가능한 단위 테스트.

- 스트리밍 지연 게이트(문장 단위 차단)
- 프롬프트 4-블록 파싱 / 스텁 마크다운의 가드레일 통과
- 의도분류 스텁(매매결정 감지)
- Claude 래퍼 스텁 스트림(파이프라인 합성 경로)
"""
from __future__ import annotations

from app.agents.claude import ClaudeClient
from app.agents.prompts import research as P
from app.agents.router import Task
from app.agents.streaming_gate import REDACTED_NOTICE, SentenceGate
from app.compliance.guard import guard_output


# ── 스트리밍 게이트 ──
def test_gate_redacts_violation_sentence_only():
    gate = SentenceGate()
    emissions: list = []
    emissions += gate.feed("삼성전자 거래량이 늘었다. ")
    emissions += gate.feed("지금 매수하세요. ")
    emissions += gate.feed("변동성을 점검한다.")
    emissions += gate.flush()

    texts = [e.text for e in emissions]
    assert any("거래량" in t for t in texts)  # 정상 문장 통과
    assert REDACTED_NOTICE in texts  # 위반 문장은 치환 표지로 방출
    assert gate.redacted_count == 1
    assert "buy_sell" in gate.categories
    # 원문 매매지시가 방출 텍스트에 남지 않아야 한다
    assert all("매수하세요" not in t for t in texts)


def test_gate_redaction_notice_survives_full_guard():
    # 게이트가 위반 문장을 치환한 '전체 텍스트'를 최종 풀 검증에 다시 통과시켜도
    # 치환 표지 자체가 규칙에 걸려 전체가 차단되면 안 된다(이중 차단 방지).
    gate = SentenceGate()
    em = gate.feed("관찰 포인트를 정리한다. ") + gate.feed("지금 매수하세요.") + gate.flush()
    full = "".join(e.text for e in em)
    assert REDACTED_NOTICE.strip() in full
    res = guard_output(full)
    assert res.blocked is False, res.categories


def test_gate_passes_clean_stream():
    gate = SentenceGate()
    out = gate.feed("관찰 포인트를 정리한다. 리스크를 점검한다.")
    out += gate.flush()
    assert gate.redacted_count == 0
    assert "".join(e.text for e in out).strip().startswith("관찰 포인트")


# ── 프롬프트 / 4-블록 ──
def test_stub_markdown_passes_guardrail_and_parses():
    ctx = {
        "name": "삼성전자",
        "symbol_norm": "005930.KS",
        "market": "KR",
        "style": "swing",
        "quote": {
            "price": 71000,
            "currency": "KRW",
            "change_pct": -1.2,
            "volume": 1000000,
            "source": "fdr",
            "as_of": "2026-06-24T00:00:00+00:00",
            "is_realtime": False,
        },
        "trend": "최근 20봉 종가 70000→71000 (구간 1.43%)",
        "news": [{"title": "삼성전자 신제품 공개", "source": "rss", "published_at": "2026-06-23"}],
    }
    md = P.stub_research_markdown(ctx)
    guard = guard_output(md)
    assert guard.blocked is False  # 스텁 산출물은 컴플라이언스 통과해야 한다

    blocks = P.parse_blocks(md)
    assert blocks["facts"] and blocks["observations"]
    assert blocks["scenarios"] and blocks["risks"]


def test_intent_detects_trade_decision():
    d = P.stub_classification("이거 지금 사도 돼?", fallback_symbol="005930")
    assert d["is_trade_decision"] is True
    assert d["intent"] == "trade_decision"
    assert d["instruments"] == ["005930"]


def test_intent_plain_research():
    d = P.stub_classification("삼성전자 요즘 어때?", fallback_symbol="005930")
    assert d["is_trade_decision"] is False
    assert d["intent"] == "research"


def test_parse_classification_from_fenced_json():
    raw = '```json\n{"intent":"research","instruments":["AAPL"],"is_trade_decision":false}\n```'
    data = P.parse_classification(raw)
    assert data and data["instruments"] == ["AAPL"]


# ── Claude 스텁 스트림(파이프라인 합성 경로) ──
async def test_claude_stub_stream_yields_text_and_final():
    client = ClaudeClient()  # ANTHROPIC_API_KEY 없음 → 스텁
    assert client.enabled is False
    chunks: list[str] = []
    final = None
    async for ev in client.stream(
        Task.RESEARCH,
        system="s",
        messages=[{"role": "user", "content": "q"}],
        stub_text="가나다라마바사아자차카타파하12345",
    ):
        if ev["type"] == "text":
            chunks.append(ev["text"])
        elif ev["type"] == "final":
            final = ev["result"]
    assert "".join(chunks) == "가나다라마바사아자차카타파하12345"
    assert final is not None and final.is_stub is True
    assert final.cost_usd == 0.0
