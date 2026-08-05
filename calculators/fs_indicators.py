"""재무 지표 순수 계산 — 성장성/수익성/안정성/현금흐름/밸류에이션(design/06).

업종 평균 무료 소스가 없어(design/21 §159 "유니버스 내 동일 테마 중앙값 자체 산출, 초기엔
자사 5y 단독 판정") 이 1차 구현은 자사 5년 단독 판정으로 축소한다 — 부채비율만 design/06 §3-4가
명시한 절대 기준선(100%/200%)을 그대로 쓴다(업종 의존 없이도 정의된 규칙이라 축소가 필요 없다).

입력은 collectors(EDGAR/DART) 공통 정규화 형태: {line: [{'year': 'YYYY', 'value': float}, ...]}
(연도 오름차순). 판정 값은 "good"|"neutral"|"caution"(design/06 §1-6 3단계, 빨강 판정 없음).
"""
from __future__ import annotations


def _pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return round((new / old - 1) * 100, 2)


def revenue_growth(financials: dict) -> dict | None:
    series = financials.get("revenue") or []
    if len(series) < 2:
        return None
    latest, prior = series[-1], series[-2]
    yoy = _pct_change(latest["value"], prior["value"])
    if yoy is None:
        return None
    judgment = "good" if yoy > 0 else ("neutral" if yoy == 0 else "caution")
    cagr = None
    if len(series) >= 4 and series[-4]["value"] > 0:
        years = int(series[-1]["year"]) - int(series[-4]["year"]) or 1
        cagr = round(((latest["value"] / series[-4]["value"]) ** (1 / years) - 1) * 100, 2)
    return {
        "latest_year": latest["year"], "value": yoy, "cagr_pct": cagr,
        "judgment": judgment, "series": series[-5:],
    }


def operating_margin(financials: dict) -> dict | None:
    revenue = financials.get("revenue") or []
    op = financials.get("operating_income") or []
    if not revenue or not op:
        return None
    by_year_rev = {r["year"]: r["value"] for r in revenue}
    margins = [
        {"year": r["year"], "value": round(r["value"] / by_year_rev[r["year"]] * 100, 2)}
        for r in op if by_year_rev.get(r["year"])
    ]
    if not margins:
        return None
    latest = margins[-1]
    own_avg = round(sum(m["value"] for m in margins) / len(margins), 2)
    delta = round(latest["value"] - own_avg, 2)
    judgment = "good" if delta >= 1 else ("caution" if delta <= -1 else "neutral")
    return {
        "latest_year": latest["year"], "value": latest["value"], "own_5y_avg": own_avg,
        "judgment": judgment, "series": margins[-5:],
    }


def debt_ratio(financials: dict) -> dict | None:
    """부채비율(design/06 §3-4) — 절대 기준선: <100% 양호 / 100~200% 중립 / >200% 주의."""
    liabilities = financials.get("liabilities") or []
    equity = financials.get("equity") or []
    if not liabilities or not equity:
        return None
    by_year_eq = {r["year"]: r["value"] for r in equity}
    ratios = [
        {"year": r["year"], "value": round(r["value"] / by_year_eq[r["year"]] * 100, 2)}
        for r in liabilities if by_year_eq.get(r["year"])
    ]
    if not ratios:
        return None
    latest = ratios[-1]
    if latest["value"] < 100:
        judgment = "good"
    elif latest["value"] <= 200:
        judgment = "neutral"
    else:
        judgment = "caution"
    return {"latest_year": latest["year"], "value": latest["value"], "judgment": judgment, "series": ratios[-5:]}


def free_cash_flow(financials: dict) -> dict | None:
    """FCF = 영업CF − CAPEX(design/06 §3-5). 3년 연속 양수→양호 / 3y 내 음수 1회→중립 /
    최근 연도 음수→주의."""
    ocf = financials.get("operating_cf") or []
    if not ocf:
        return None
    by_year_capex = {r["year"]: r["value"] for r in (financials.get("capex") or [])}
    rows = [{"year": r["year"], "value": round(r["value"] - by_year_capex.get(r["year"], 0), 2)} for r in ocf]
    latest = rows[-1]
    recent3 = rows[-3:]
    if latest["value"] < 0:
        judgment = "caution"
    elif all(r["value"] >= 0 for r in recent3):
        judgment = "good"
    else:
        judgment = "neutral"
    return {"latest_year": latest["year"], "value": latest["value"], "judgment": judgment, "series": rows[-10:]}


def _by_year(series) -> dict:
    return {r["year"]: r["value"] for r in (series or [])}


def valuation_triangle(financials: dict, close_price: float | None) -> dict | None:
    """ROE·PER·PBR 삼각형 — 세 지표와 그 원천값(주가·EPS·BPS)을 한 컨테이너로.

    셋은 독립 지표가 아니라 한 항등식의 세 변이다(꼭짓점 = 주가·EPS·BPS):

        PER = 주가 ÷ EPS,  PBR = 주가 ÷ BPS,  ROE = EPS ÷ BPS   ⇒   PBR = PER × ROE

    BPS는 발행주식수를 따로 수집하지 않고 유도한다 — 주식수를 s라 하면
    EPS = 순이익/s, BPS = 자본총계/s 이므로 s가 소거된다:

        BPS = EPS × (자본총계 ÷ 순이익)

    ⚠ 이 유도는 EPS(희석 기준)와 순이익(총액, 비지배지분 포함)의 분모가 같다고 보는 근사다.
    비지배지분이 큰 기업일수록 오차가 커진다 — 발행주식수를 직접 수집하기 전까지의 축소이며
    화면 캡션으로 고지한다(design/21 §159의 결측 허용 정신과 같은 원칙).

    판정(judgment)은 붙이지 않는다 — 밸류에이션은 업종 평균 없이 절대 기준을 세울 수 없다
    (design/06 §1-6, valuation_per과 동일).
    """
    ni = _by_year(financials.get("net_income"))
    eq = _by_year(financials.get("equity"))
    ep = _by_year(financials.get("eps"))

    full = sorted(set(ni) & set(eq) & set(ep))
    partial = sorted(set(ni) & set(eq))
    year = full[-1] if full else (partial[-1] if partial else None)
    if year is None:
        return None

    net_income, equity = ni[year], eq[year]
    eps = ep.get(year)
    notes: list[str] = []

    roe = bps = None
    if equity > 0:
        roe = round(net_income / equity * 100, 2)
        if eps is not None and net_income != 0:
            derived = eps * equity / net_income
            if derived > 0:
                bps = round(derived, 2)
    else:
        notes.append("자본총계 0 이하(자본잠식) — ROE·BPS 산출 불가")

    if eps is None:
        notes.append("EPS 미수집 — PER·PBR·BPS 산출 불가")
    elif eps <= 0:
        notes.append("적자(EPS 0 이하) — PER 산출 불가")
    if close_price is None:
        notes.append("종가 미수집 — PER·PBR 산출 불가")

    per = round(close_price / eps, 2) if (close_price and eps and eps > 0) else None
    pbr = round(close_price / bps, 2) if (close_price and bps) else None

    roe_series = [
        {"year": y, "value": round(ni[y] / eq[y] * 100, 2)}
        for y in sorted(set(ni) & set(eq)) if eq[y] > 0
    ][-5:]

    return {
        "latest_year": year,
        "price": close_price,
        "eps": eps,
        "bps": bps,
        "roe": roe,
        "per": per,
        "pbr": pbr,
        "roe_series": roe_series,
        "note": " · ".join(notes) or None,
    }


def valuation_per(financials: dict, close_price: float | None) -> dict | None:
    """PER = 종가 ÷ 최근 EPS. 판정 미적용(design/06 §1-6) — 5년 밴드는 장기 주가 이력이 별도로
    필요해 이 1차 구현에서는 생략하고 단순 배수만 제공한다(정직한 축소, 캡션으로 고지)."""
    eps_series = financials.get("eps") or []
    if not eps_series or not close_price:
        return None
    latest_eps = eps_series[-1]["value"]
    if latest_eps <= 0:
        return {"latest_year": eps_series[-1]["year"], "eps": latest_eps, "per": None, "note": "적자 — PER 산출 불가"}
    return {"latest_year": eps_series[-1]["year"], "eps": latest_eps, "per": round(close_price / latest_eps, 2), "note": None}
