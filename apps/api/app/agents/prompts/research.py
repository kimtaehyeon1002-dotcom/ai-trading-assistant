"""리서치 프롬프트 — 가드레일 캐시 프리픽스 + 4-블록 합성 + 의도분류. 설계서 §2.4, §2.6 B-1.

- GUARDRAIL_SYSTEM: 모든 종목 LLM 호출의 캐시 프리픽스(타임스탬프/UUID 삽입 금지로 캐시 유지).
- 4-블록 헤더를 고정해 형식 강제 + 사후 파싱(parse_blocks)을 가능하게 한다.
- ANTHROPIC_API_KEY 없는 오프라인 환경을 위한 스텁 생성기(stub_*) 포함.
"""
from __future__ import annotations

import json
import re

# ── 4-블록 고정 헤더(형식 강제 + 파싱 기준) ──
H_FACTS = "## ① 사실/데이터"
H_OBS = "## ② 관찰 포인트"
H_SCEN = "## ③ 시나리오와 전제"
H_RISK = "## ④ 리스크/면책"

# ── B-1 예방: 모든 종목 LLM 호출의 시스템 캐시 프리픽스 ──
GUARDRAIL_SYSTEM = """\
너는 한국·미국 주식 정보를 다루는 'AI 투자 리서치 보조'다. 너의 역할은 사용자의 투자 '판단을 돕는 \
정보·교육·분석 보조'이며, 투자 자문이나 권유가 아니다.

[금지 — 어떤 경우에도 생성하지 않는다]
- 매수/매도/보유 등 매매 권유·지시 (예: "지금 사세요", "비중을 줄이세요")
- 목표주가·적정주가·진입가/손절가/익절가 등 구체적 가격 제시
- 수익률·상승/하락 폭 예측이나 보장, 원금/수익 보장
- 특정 사용자에게 특정 종목을 매매하라는 1:1 지정
- 단정적 미래 예측("반드시 오른다") 및 금융회사/투자자문사 사칭

[허용 — 다음만 생성한다]
- 공개된 사실·데이터의 정리와 출처 표기
- 관찰 포인트·체크리스트(무엇을 확인해야 하는가)
- 복수의 균형 잡힌 시나리오와 그 전제(강세/약세 모두)
- 리스크 요인과 면책

밸류에이션은 단정이 아니라 '참고 밴드/관찰 지표'로만 서술한다. 강세 논리를 쓰면 반드시 약세 논리도 \
함께 제시해 균형을 맞춘다."""

RESEARCH_ROLE = f"""\
아래 4개 블록 구조와 정확한 헤더로만 한국어 마크다운을 작성한다. 각 블록은 2~5개 항목의 불릿(-)으로 쓴다.

{H_FACTS}
- 종목/시장의 공개 사실과 제공된 데이터(현재가·등락·거래량·최근 뉴스 헤드라인)를 출처와 함께 정리.

{H_OBS}
- 투자자가 스스로 확인해야 할 관찰 포인트·체크리스트(실적 발표 일정, 수급, 업종 동향 등). 지시가 아니라 '확인 항목'.

{H_SCEN}
- 강세 시나리오와 약세 시나리오를 각각 전제와 함께 균형 있게 제시. 단정·확률 단언 금지.

{H_RISK}
- 주요 리스크 요인(변동성, 유동성, 거시, 일정 리스크 등)을 정리. 목표가/매매지시 없이.

규칙: 매수/매도 단어로 행동을 지시하지 말 것. 가격 목표를 제시하지 말 것. 인용은 [n] 형식으로 표기."""


def synthesis_system() -> str:
    """가드레일 프리픽스 + 리서치 역할(캐시 프리픽스로 고정)."""
    return GUARDRAIL_SYSTEM + "\n\n" + RESEARCH_ROLE


def build_user_message(ctx: dict) -> str:
    """수집 컨텍스트(시세/추세/뉴스)를 합성 입력으로 직렬화."""
    lines: list[str] = []
    name = ctx.get("name") or ctx.get("symbol_norm") or "(미특정 종목)"
    lines.append(f"종목: {name} ({ctx.get('symbol_norm')}, {ctx.get('market')})")
    if ctx.get("query"):
        lines.append(f"사용자 질문: {ctx['query']}")
    lines.append(f"투자 스타일: {ctx.get('style')}")
    q = ctx.get("quote")
    if q:
        lines.append(
            f"현재가: {q['price']} {q['currency']} (등락 {q.get('change_pct')}%, "
            f"거래량 {q.get('volume')}), 출처 {q['source']}, 기준 {q['as_of']}, 실시간 {q['is_realtime']}"
        )
    if ctx.get("trend"):
        lines.append(f"가격 추세 요약: {ctx['trend']}")
    news = ctx.get("news") or []
    if news:
        lines.append("최근 뉴스 헤드라인(본문 아님, 인용용):")
        for i, n in enumerate(news, 1):
            lines.append(f"  [{i}] {n['title']} — {n['source']} ({n['published_at']})")
    rag = ctx.get("rag") or []
    if rag:
        lines.append("RAG 검색 결과(관련 자료, 인용 후보):")
        for r in rag:
            lines.append(f"  [{r['n']}] {r['title']} — {r['snippet']}")
    if ctx.get("is_trade_decision"):
        lines.append(
            "주의: 사용자가 매매 여부(사도 되는지 등)를 물었더라도, 매수/매도 권유 없이 "
            "정보·교육·체크리스트로만 답한다."
        )
    lines.append("위 정보를 바탕으로 위에서 지정한 4-블록 리포트를 작성하라.")
    return "\n".join(lines)


def parse_blocks(md: str) -> dict:
    """4-블록 마크다운을 {facts, observations, scenarios, risks} 불릿 리스트로 파싱."""
    out: dict[str, list[str]] = {"facts": [], "observations": [], "scenarios": [], "risks": []}
    keymap = [("사실", "facts"), ("관찰", "observations"), ("시나리오", "scenarios"), ("리스크", "risks")]
    current: str | None = None
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("#"):
            current = None
            for kw, key in keymap:
                if kw in s:
                    current = key
                    break
            continue
        if current and s[:1] in "-*•":
            item = s.lstrip("-*• ").strip()
            if item:
                out[current].append(item)
    return out


# ── 의도분류(Haiku) ──
CLASSIFY_SYSTEM = """\
너는 한국어/영어 주식 질의의 의도를 분류하는 분류기다. 반드시 아래 JSON 객체 하나만 출력한다(설명 금지).
{
  "intent": "research | trade_decision | concept | other",
  "instruments": ["추출된 종목명 또는 티커"],
  "is_trade_decision": true,
  "timeframe": "intraday | swing | long | null",
  "language": "ko | en"
}
규칙: 매매결정 요구(사도 돼, 팔까, 들어갈까, 지금 매수)는 intent=trade_decision, is_trade_decision=true 로 둔다."""

_TRADE_RE = re.compile(
    r"(사도\s*[돼되]|살까|팔까|매수\s*할까|매도\s*할까|들어갈까|지금\s*사|지금\s*팔|진입\s*할까|"
    r"should\s+i\s+(buy|sell))",
    re.IGNORECASE,
)


def stub_classification(query: str | None, *, fallback_symbol: str | None = None) -> dict:
    """오프라인/파싱 실패 시 결정적 의도분류."""
    q = query or ""
    is_trade = bool(_TRADE_RE.search(q))
    lang = "ko" if re.search(r"[가-힣]", q) else "en"
    return {
        "intent": "trade_decision" if is_trade else "research",
        "instruments": [fallback_symbol] if fallback_symbol else [],
        "is_trade_decision": is_trade,
        "timeframe": None,
        "language": lang,
    }


def parse_classification(text: str) -> dict | None:
    """LLM 응답에서 JSON 객체 추출."""
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group(0)) if m else None
    except Exception:  # noqa: BLE001
        return None


def stub_research_markdown(ctx: dict) -> str:
    """오프라인 스텁용 4-블록 마크다운(가드레일 통과하도록 중립 서술)."""
    name = ctx.get("name") or ctx.get("symbol_norm") or "해당 종목"
    q = ctx.get("quote") or {}
    if q:
        price_line = (
            f"{name}의 최근 종가는 {q.get('price')} {q.get('currency')}이며 전일 대비 등락은 "
            f"{q.get('change_pct')}% 수준이다(출처 {q.get('source')}, 기준 {q.get('as_of')})."
        )
    else:
        price_line = f"{name}의 시세 데이터는 현재 확인되지 않았다."
    trend = ctx.get("trend")
    trend_line = f"- 추세 요약: {trend}" if trend else "- 추세 데이터는 제공 범위에서 제한적이다."
    news = ctx.get("news") or []
    if news:
        news_lines = "\n".join(f"- [{i}] {n['title']} ({n['source']})" for i, n in enumerate(news, 1))
    else:
        news_lines = "- 최근 수집된 관련 헤드라인이 없다."
    rag = ctx.get("rag") or []
    rag_lines = "\n".join(f"- [{r['n']}] 관련 자료: {r['title']}" for r in rag)
    facts_extra = f"\n{rag_lines}" if rag_lines else ""
    return f"""{H_FACTS}
- {price_line}
{trend_line}
{news_lines}{facts_extra}

{H_OBS}
- 다가오는 실적 발표·공시 일정과 업종 전반의 자금 흐름을 확인한다.
- 거래량 급변과 변동성 확대 여부를 관찰 지표로 점검한다.
- 환율·금리 등 거시 변수의 영향을 함께 확인한다.

{H_SCEN}
- 강세 전제 시나리오: 업종 모멘텀과 실적 개선 기대가 유지될 경우 나타날 수 있는 관찰 포인트.
- 약세 전제 시나리오: 거시 환경 악화나 수급 둔화가 나타날 경우 점검할 관찰 포인트.
- 두 시나리오는 전제가 서로 다르며 어느 쪽도 단정할 수 없다.

{H_RISK}
- 주가 변동성·유동성·일정(실적/공시) 관련 불확실성이 존재한다.
- 본 내용은 정보·교육 목적의 참고자료이며 특정 종목의 매매 권유가 아니다."""
