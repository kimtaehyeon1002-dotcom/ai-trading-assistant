"""포트폴리오 분석 프롬프트 — 분산 개념·관찰 포인트(리밸런싱 지시 금지). 설계서 §2.4.

4-블록: ①구성·노출 사실 ②집중·편중 관찰 ③분산 관점 시나리오·전제 ④리스크/면책.
"사라/팔아라/비중을 줄여라" 같은 매매·리밸런싱 지시는 하지 않는다.
"""
from __future__ import annotations

from app.agents.prompts.research import GUARDRAIL_SYSTEM

H_COMP = "## ① 구성·노출 (사실)"
H_OBS = "## ② 집중·편중 관찰"
H_SCEN = "## ③ 분산 관점 시나리오·전제"
H_RISK = "## ④ 리스크/면책"

PORTFOLIO_ROLE = f"""\
너는 보유 포트폴리오의 위험·편중을 설명하는 정보 보조다. 코드로 계산된 지표(비중·집중도 HHI·
섹터/시장/통화 노출)를 사실대로 해석하고, 분산이라는 '일반 개념'과 관찰 포인트만 제시한다.
특정 종목을 사라/팔라거나 '비중을 줄여라/늘려라' 같은 리밸런싱 지시는 하지 않는다.

아래 4개 블록과 정확한 헤더로 한국어 마크다운을 쓴다(각 2~5개 불릿).

{H_COMP}
- 총 평가액·종목수·상위 비중·섹터/시장/통화 노출을 사실대로 요약(기준통화 표기).

{H_OBS}
- 집중도(HHI·유효 종목수·상위 비중)와 특정 섹터/국가/통화 편중을 '관찰'로 기술. 단정 금지.

{H_SCEN}
- 분산이라는 일반 개념의 관점에서 점검할 시나리오와 전제(예: 특정 노출이 클 때 함께 움직일 위험).
  특정 종목 매매·목표 비중 지시 금지.

{H_RISK}
- 집중·통화·유동성 등 리스크와, 본 분석이 매매 권유가 아니라는 면책.

규칙: 매수/매도·목표가·목표 비중·리밸런싱 지시 금지. 통화는 KRW/USD 등으로 표기."""


def portfolio_system() -> str:
    return GUARDRAIL_SYSTEM + "\n\n" + PORTFOLIO_ROLE


def _fmt_exposure(b: dict) -> str:
    return ", ".join(f"{k} {round(v['weight']*100)}%" for k, v in b.items()) or "—"


def build_portfolio_user(metrics: dict) -> str:
    lines = ["[코드 계산 지표]"]
    lines.append(
        f"기준통화 {metrics['base_currency']}, 총 평가액 {metrics['total_value']}, "
        f"종목수 {metrics['n_positions']}, HHI {metrics['hhi']}(집중도 {metrics['concentration_band']}), "
        f"유효 종목수 {metrics['effective_n']}, 상위1 {round(metrics['top1_weight']*100)}%, "
        f"상위3 {round(metrics['top3_weight']*100)}%"
    )
    lines.append(f"섹터 노출: {_fmt_exposure(metrics.get('by_sector', {}))}")
    lines.append(f"시장 노출: {_fmt_exposure(metrics.get('by_market', {}))}")
    lines.append(f"통화 노출: {_fmt_exposure(metrics.get('by_currency', {}))}")
    if metrics.get("valuation_note"):
        lines.append(f"평가 주의: {metrics['valuation_note']}")
    lines.append("위 지표로 4-블록 분석을 작성하라(분산 개념·관찰만, 리밸런싱 지시 금지).")
    return "\n".join(lines)


def parse_portfolio_blocks(md: str) -> dict:
    out: dict[str, list[str]] = {"composition": [], "observations": [], "scenarios": [], "risks": []}
    keymap = [("구성", "composition"), ("관찰", "observations"), ("시나리오", "scenarios"), ("리스크", "risks")]
    current = None
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


def stub_portfolio_markdown(metrics: dict) -> str:
    sec = _fmt_exposure(metrics.get("by_sector", {}))
    mkt = _fmt_exposure(metrics.get("by_market", {}))
    cur = _fmt_exposure(metrics.get("by_currency", {}))
    return f"""{H_COMP}
- 기준통화 {metrics['base_currency']}, 총 평가액 {metrics['total_value']}, 보유 {metrics['n_positions']}종목.
- 상위 1종목 비중 {round(metrics['top1_weight']*100)}%, 상위 3종목 {round(metrics['top3_weight']*100)}%.
- 섹터 노출: {sec} / 시장 노출: {mkt} / 통화 노출: {cur}.

{H_OBS}
- 집중도(HHI) {metrics['hhi']}, 유효 종목수 {metrics['effective_n']} → 집중도 관찰 밴드 '{metrics['concentration_band']}'.
- 특정 섹터·국가·통화로 노출이 치우쳐 있는지 관찰 대상으로 본다.
- 상위 종목 비중이 높을수록 개별 종목 변동이 전체에 미치는 영향이 커진다(관찰).

{H_SCEN}
- 분산 관점 전제: 노출이 한쪽에 집중되면 해당 요인 악화 시 함께 흔들릴 수 있다.
- 반대 전제: 분산이 충분하면 개별 충격의 전체 영향은 완화될 수 있다.
- 두 전제 모두 가정이며 특정 종목 매매·목표 비중을 제시하지 않는다.

{H_RISK}
- 집중·통화·유동성 리스크가 존재하며 시세 기준 평가액은 변동한다.
- 본 분석은 정보·교육 목적의 관찰이며 매매 권유나 리밸런싱 지시가 아니다."""
