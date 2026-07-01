"""모닝리포트 프롬프트 — 가드레일 프리픽스 + 브리핑 역할 + 스텁. 설계서 §1.3-A, §2.4, §2.5.

섹션: ①글로벌 지수/환율·유가 ②미국 강세 테마(관찰 지표) ③예상 한국 강세 테마(US→KR 매핑)
④핵심 뉴스 3~5 ⑤영향 분석(균형). 테마는 '관찰', 종목 단정 금지.
"""
from __future__ import annotations

from app.agents.prompts.research import GUARDRAIL_SYSTEM

H_MARKET = "## ① 글로벌 지수·환율"
H_US = "## ② 미국 강세 테마 (관찰 지표)"
H_KR = "## ③ 예상 한국 강세 테마 (US→KR 매핑)"
H_NEWS = "## ④ 핵심 뉴스"
H_IMPACT = "## ⑤ 영향 분석 (균형)"

MORNING_ROLE = f"""\
너는 아침 시장 브리핑을 작성하는 정보 보조다. 아래 5개 섹션과 정확한 헤더로 한국어 마크다운을 쓴다.
테마 강세는 '관찰 지표'(코드로 계산된 스코어)로 서술하고 매수 신호로 표현하지 않는다.
강세 서술에는 반드시 약세/리스크 측면을 함께 둔다. 목표가·매매지시·수익률 예측 금지.

{H_MARKET}
- 제공된 환율(USD/KRW) 등 거시 데이터를 사실 위주로 정리.

{H_US}
- 제공된 미국 테마 스코어(score·rank)를 관찰 지표로 정리(상위부터). 매수 권유 아님.

{H_KR}
- 미국 강세 테마에 대응하는 한국 테마를 상관·전이 '시나리오'로 제시(추천 아님, 전제 명시).

{H_NEWS}
- 핵심 뉴스 3~5개를 제목+출처+[n] 인용으로(본문 아님).

{H_IMPACT}
- 위 정보가 시장에 줄 수 있는 영향 시나리오를 강세/약세 균형 있게. 단정 금지."""


def morning_system() -> str:
    return GUARDRAIL_SYSTEM + "\n\n" + MORNING_ROLE


def _fmt_themes(themes: list[dict]) -> str:
    if not themes:
        return "- 제공된 테마 스코어가 없다(데이터 준비 중)."
    return "\n".join(
        f"- {t['theme']} — score {t['score']:.0f} (rank {t['rank']})" for t in themes
    )


def build_morning_user(ctx: dict) -> str:
    lines = [f"기준일: {ctx.get('report_date')}"]
    fx = ctx.get("fx")
    if fx:
        lines.append(f"환율 USD/KRW: {fx['rate']} (출처 {fx['source']}, 기준 {fx['as_of']})")
    lines.append("미국 테마 스코어:")
    for t in ctx.get("themes_us") or []:
        lines.append(f"  - {t['theme']} score {t['score']:.1f} rank {t['rank']}")
    lines.append("한국 테마 스코어:")
    for t in ctx.get("themes_kr") or []:
        lines.append(f"  - {t['theme']} score {t['score']:.1f} rank {t['rank']}")
    lines.append("핵심 뉴스(본문 아님):")
    for i, n in enumerate(ctx.get("news") or [], 1):
        lines.append(f"  [{i}] {n['title']} — {n['source']} ({n['published_at']})")
    lines.append("위 데이터로 5-섹션 모닝리포트를 작성하라(테마는 관찰 지표, 매수 신호 아님).")
    return "\n".join(lines)


def stub_morning_markdown(ctx: dict) -> str:
    fx = ctx.get("fx")
    fx_line = (
        f"- USD/KRW 환율은 {fx['rate']} 수준이다(출처 {fx['source']}, 기준 {fx['as_of']})."
        if fx
        else "- 환율 데이터는 현재 확인되지 않았다."
    )
    news = ctx.get("news") or []
    news_lines = (
        "\n".join(f"- [{i}] {n['title']} ({n['source']})" for i, n in enumerate(news, 1))
        if news
        else "- 수집된 핵심 뉴스가 없다."
    )
    return f"""{H_MARKET}
{fx_line}
- 글로벌 지수·유가 등 추가 거시 지표는 데이터 제공 범위에서 제한적이다.

{H_US}
{_fmt_themes(ctx.get('themes_us') or [])}
- 위 스코어는 가격·거래량·관심도·뉴스 신호를 종합한 관찰 지표이며 투자 권유가 아니다.

{H_KR}
{_fmt_themes(ctx.get('themes_kr') or [])}
- 미국 강세 테마의 한국 전이는 전제가 성립할 때의 시나리오일 뿐 단정할 수 없다.

{H_NEWS}
{news_lines}

{H_IMPACT}
- 강세 전제: 테마 모멘텀과 우호적 거시가 이어질 경우 관찰할 포인트.
- 약세 전제: 거시 악화·수급 둔화 시 점검할 포인트.
- 본 브리핑은 정보·교육 목적의 참고자료이며 매매 권유가 아니다."""
