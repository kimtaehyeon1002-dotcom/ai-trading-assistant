"""인라인 SVG 스파크라인 — 순수 함수(외부 의존 0, hex 리터럴 0).

색은 CSS 변수(`--market-up/down/flat`)로만 지정한다(design/22 R6 "팔레트 밖 hex 금지").
방향은 첫 값 대비 마지막 값으로 판정한다 — 등락률과 선 색이 어긋나 보이지 않게 하기 위함이다.

design/25: TA 전용이던 ta_repository.sparkline_svg를 Macro 시세 스트립도 쓸 수 있게 일반화해
여기로 옮겼다(ta_repository는 이 함수에 위임한다 — 호출부 시그니처 불변).

design/25 §10(가시성 개선): 기준선 + 면적 채움을 추가했다. 스파크라인은 min/max 정규화라
**모든 계열이 같은 진폭으로 그려진다** — 환율 0.1% 움직임과 천연가스 30% 급등이 똑같이 보인다.
기준선(구간 첫 값)을 그려 주면 "위로 갔나 아래로 갔나"가 즉시 읽히고, 면적이 방향을 강화한다.
크기(진짜 몇 %인가)는 숫자로 병기해야 하며 그건 호출부 책임이다(design/00 R4의 연장 —
색·모양만으로 정보를 전달하지 않는다).
"""
from __future__ import annotations

MAX_POINTS = 60


def _direction_var(points: list[float]) -> str:
    delta = points[-1] - points[0]
    if delta > 0:
        return "var(--market-up)"
    if delta < 0:
        return "var(--market-down)"
    return "var(--market-flat)"


def sparkline_svg(
    closes: list[float],
    width: int = 952,
    height: int = 72,
    label: str = "종가 추이",
    css_class: str = "v2-ta-spark",
    color_by_direction: bool = False,
    max_points: int = MAX_POINTS,
    baseline: bool = False,
) -> str:
    """종가 리스트 → 폴리라인 SVG 문자열. 점이 2개 미만이면 빈 문자열(선을 그릴 수 없음).

    color_by_direction=False면 기존 TA 동작(항상 flat 색)을 유지한다.
    baseline=True면 구간 첫 값 위치에 점선 기준선을 긋고 선과 기준선 사이를 옅게 채운다.
    """
    pts = closes[-max_points:] if len(closes) > max_points else closes
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)

    def y_of(v: float) -> float:
        return height - ((v - lo) / span) * height

    # 선이 위아래 테두리에 붙어 잘려 보이지 않도록 여백을 준다(stroke 두께의 절반 이상).
    pad = 2.0
    inner = height - pad * 2

    def y_padded(v: float) -> float:
        return pad + (1 - (v - lo) / span) * inner

    coords = " ".join(f"{i * step:.1f},{y_padded(v):.1f}" for i, v in enumerate(pts))
    stroke = _direction_var(pts) if color_by_direction else "var(--market-flat)"

    parts = [
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'role="img" aria-label="{label}" class="{css_class}">'
    ]
    if baseline:
        base_y = y_padded(pts[0])
        # 면적: 선 → 기준선으로 닫은 폴리곤. 방향색을 옅게 깔아 상승/하락이 한눈에 들어온다.
        area = f"0,{base_y:.1f} {coords} {width},{base_y:.1f}"
        parts.append(
            f'<polygon points="{area}" fill="{stroke}" fill-opacity="0.14" stroke="none"/>'
        )
        parts.append(
            f'<line x1="0" y1="{base_y:.1f}" x2="{width}" y2="{base_y:.1f}" '
            f'stroke="var(--market-flat)" stroke-width="1" stroke-dasharray="3 3" '
            f'stroke-opacity="0.55"/>'
        )
    parts.append(
        f'<polyline points="{coords}" fill="none" stroke="{stroke}" '
        f'stroke-width="{2 if baseline else 1.5}" stroke-linejoin="round" stroke-linecap="round"'
        f' vector-effect="non-scaling-stroke"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def period_change_pct(closes: list[float], max_points: int = MAX_POINTS) -> float | None:
    """차트가 실제로 그리는 구간의 등락률 — 그래프 옆에 병기할 숫자.

    스파크라인은 진폭이 정규화돼 크기를 못 보여주므로, 이 숫자가 없으면 그림이 거짓말을 한다.
    """
    pts = closes[-max_points:] if len(closes) > max_points else closes
    if len(pts) < 2 or not pts[0]:
        return None
    return round((pts[-1] / pts[0] - 1) * 100, 2)
