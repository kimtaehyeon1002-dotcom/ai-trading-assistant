"""자산 지표 순수 계산 — 총자산·계좌 비중·목표달성률(design/08).

정규화된 계좌 dict({"role","label","sub_label","balance_krw","change_pct","eval_pnl_krw",
"eval_pnl_pct", ...})를 받아 집계만 한다. Envelope 유사 컨테이너 조립·암호화는
repositories/asset_repository가 담당한다(calculators는 부작용 없는 순수 함수).
"""
from __future__ import annotations


def total_assets(accounts: list[dict]) -> float:
    return round(sum(a["balance_krw"] for a in accounts if a.get("balance_krw") is not None), 2)


def with_weights(accounts: list[dict]) -> list[dict]:
    """각 계좌에 weight_pct(전체 자산 대비 비중) 부여. 원본 accounts는 불변."""
    total = total_assets(accounts)
    if not total:
        return [{**a, "weight_pct": None} for a in accounts]
    return [
        {**a, "weight_pct": round(a["balance_krw"] / total * 100, 1) if a.get("balance_krw") is not None else None}
        for a in accounts
    ]


def goal_progress_pct(current: float, goal_amount: float | None) -> float | None:
    if not goal_amount:
        return None
    return round(current / goal_amount * 100, 1)


def currency_exposure(accounts: list[dict]) -> list[dict]:
    """통화별 노출 — {"currency","amount_krw","pct"}. native_currency 없는 계좌는 KRW로 취급."""
    by_ccy: dict[str, float] = {}
    for a in accounts:
        if a.get("balance_krw") is None:
            continue
        ccy = a.get("native_currency") or "KRW"
        by_ccy[ccy] = by_ccy.get(ccy, 0.0) + a["balance_krw"]
    total = sum(by_ccy.values())
    if not total:
        return []
    return [
        {"currency": ccy, "amount_krw": round(amt, 2), "pct": round(amt / total * 100, 1)}
        for ccy, amt in sorted(by_ccy.items(), key=lambda kv: kv[1], reverse=True)
    ]
