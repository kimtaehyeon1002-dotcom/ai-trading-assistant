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
