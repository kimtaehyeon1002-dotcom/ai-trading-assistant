"""Trading Coach 프롬프트 — 교육형 회고(개별 종목 권유·목표가 금지). 설계서 §1.3-C, §2.4.

4-블록: ①성과 요약(지표) ②행동 패턴/편향 관찰 ③리스크관리 체크리스트(일반 교육) ④리스크/면책.
'지금 다시 살까?' 류는 매매 권유가 아니라 과거 기록 기반 교육적 관찰로만 응답.
"""
from __future__ import annotations

from app.agents.prompts.research import GUARDRAIL_SYSTEM

H_PERF = "## ① 성과 요약(지표)"
H_PAT = "## ② 행동 패턴 관찰"
H_CHK = "## ③ 리스크관리 체크리스트"
H_RISK = "## ④ 리스크/면책"

COACH_ROLE = f"""\
너는 사용자의 과거 매매 기록을 돌아보게 돕는 '교육형 트레이딩 코치'다. 개별 종목을 사라/팔라거나 \
목표가·진입가를 제시하지 않는다. 코드로 계산된 지표(사실)를 해석하고, 행동 패턴(편향)과 일반적인 \
리스크관리 원칙을 교육적으로 설명한다.

아래 4개 블록과 정확한 헤더로 한국어 마크다운을 쓴다(각 2~5개 불릿).

{H_PERF}
- 제공된 지표(거래수·승률·순손익·손익비·기대값·최대 연속손실·최대 낙폭)를 사실대로 요약.

{H_PAT}
- 포지션(롱/숏) 편중, 종목 집중, 연속 손실 후 과잉 거래 경향 등 '관찰'만. 단정/예측 금지.

{H_CHK}
- 손실 한도·일관성·기대값 관점의 일반 리스크관리 점검 항목(교육). 특정 종목 행동 지시 금지.

{H_RISK}
- 과거 성과는 미래를 보장하지 않으며, 본 분석은 매매 권유가 아니라는 점 등 리스크·면책.

규칙: 매수/매도 등 행동 지시, 목표가·진입가·수익률 예측, 1:1 종목 지정 금지. 포지션은 한국어 '롱/숏'으로 표기."""


def coach_system() -> str:
    return GUARDRAIL_SYSTEM + "\n\n" + COACH_ROLE


# 포지션 라벨 한글화(영문 long/short는 가드레일 LONG/SHORT 패턴에 오탐되므로 출력 텍스트에선 롱/숏)
_POS_KR = {"long": "롱", "short": "숏", "unknown": "미상"}


def _fmt_buckets(b: dict, *, localize_pos: bool = False) -> str:
    items = []
    for k, v in b.items():
        label = _POS_KR.get(k, k) if localize_pos else k
        items.append(f"{label}({v['n']}건, ${round(v['net_pnl'],1)})")
    return ", ".join(items) or "—"


def build_coach_user(metrics: dict, *, question: str | None, is_trade_decision: bool) -> str:
    lines = ["[코드 계산 지표]"]
    lines.append(
        f"거래수 {metrics['n_trades']} (승 {metrics['n_wins']}·패 {metrics['n_losses']}·무 {metrics['n_draws']}), "
        f"승률 {metrics['win_rate']}, 순손익 ${metrics['net_pnl']}, 손익비 {metrics['profit_factor']}, "
        f"기대값 ${metrics['expectancy']}, 최대 연속손실 {metrics['max_loss_streak']}, 최대낙폭 ${metrics['max_drawdown']}"
    )
    lines.append(f"포지션별: {_fmt_buckets(metrics.get('by_position', {}), localize_pos=True)}")
    lines.append(f"종목별: {_fmt_buckets(metrics.get('by_symbol', {}))}")
    lines.append(f"요일별: {_fmt_buckets(metrics.get('by_weekday', {}))}")
    if metrics.get("unavailable"):
        lines.append(f"데이터 부족으로 계산 불가: {', '.join(metrics['unavailable'])}")
    if question:
        lines.append(f"사용자 질문: {question}")
    if is_trade_decision:
        lines.append(
            "주의: 사용자가 매매 여부를 물었더라도 권유하지 말고, 과거 기록 기반 교육적 관찰과 "
            "일반 리스크관리로만 답한다."
        )
    lines.append("위 지표로 4-블록 교육형 회고를 작성하라.")
    return "\n".join(lines)


def parse_coach_blocks(md: str) -> dict:
    out: dict[str, list[str]] = {"performance": [], "patterns": [], "checklist": [], "risks": []}
    keymap = [("성과", "performance"), ("패턴", "patterns"), ("체크리스트", "checklist"), ("리스크", "risks")]
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


def stub_coach_markdown(metrics: dict, *, is_trade_decision: bool = False) -> str:
    redirect = (
        "- 매매 여부 질문은 권유 대상이 아니므로, 아래는 과거 기록 기반 교육적 관찰만 제공한다.\n"
        if is_trade_decision
        else ""
    )
    pos = _fmt_buckets(metrics.get("by_position", {}), localize_pos=True)
    sym = _fmt_buckets(metrics.get("by_symbol", {}))
    return f"""{H_PERF}
{redirect}- 총 {metrics['n_trades']}건(승 {metrics['n_wins']}·패 {metrics['n_losses']}·무 {metrics['n_draws']}), 승률 {metrics['win_rate']}.
- 순손익 ${metrics['net_pnl']}, 손익비 {metrics['profit_factor']}, 거래당 기대값 ${metrics['expectancy']}.
- 최대 연속 손실 {metrics['max_loss_streak']}회, 누적손익 기준 최대 낙폭 ${metrics['max_drawdown']}.

{H_PAT}
- 포지션별 성과: {pos} — 한쪽으로 치우쳤는지 점검 대상으로 본다.
- 종목별 성과: {sym} — 특정 종목 집중도가 높은지 관찰한다.
- 연속 손실 직후 거래 빈도가 늘었는지(과잉 거래 경향)를 스스로 점검한다.

{H_CHK}
- 거래별 최대 허용 손실 한도를 미리 정하고 일관되게 지켰는지 점검한다.
- 승률과 손익비의 균형(기대값) 관점에서 본인 규칙을 검토한다.
- 연속 손실 구간에서 감정적 대응을 줄이기 위한 사전 규칙을 마련한다.

{H_RISK}
- 본 분석은 과거 기록의 통계 요약·행동 관찰이며 특정 종목·시점의 매매 권유가 아니다.
- 과거 성과는 미래를 보장하지 않으며 모든 거래에는 손실 위험이 있다."""
