"""자산 지표 순수 계산 — 총자산·계좌 비중·목표달성률(design/08).

정규화된 계좌 dict({"role","label","sub_label","balance_krw","change_pct","eval_pnl_krw",
"eval_pnl_pct", ...})를 받아 집계만 한다. Envelope 유사 컨테이너 조립·암호화는
repositories/asset_repository가 담당한다(calculators는 부작용 없는 순수 함수).
"""
from __future__ import annotations


def total_assets(accounts: list[dict]) -> float | None:
    """확보된 계좌 잔고의 합. 확보 계좌가 하나도 없으면 None(0원이 아니다).

    0을 돌려주면 "총자산 ₩0"이 사실처럼 렌더되고 스냅샷 원장까지 오염된다 — 결측은
    0이 아니라 '모름'이므로 None으로 강등하고 표시면에서 생략한다(결측 문법)."""
    present = [a["balance_krw"] for a in accounts if a.get("balance_krw") is not None]
    return round(sum(present), 2) if present else None


def covered_roles(accounts: list[dict]) -> tuple[list[str], list[str]]:
    """(확보된 계좌 role, 결측 계좌 role) — 발행 여부 판단과 부분합 고지의 근거."""
    covered = [a["role"] for a in accounts if a.get("balance_krw") is not None]
    missing = [a["role"] for a in accounts if a.get("balance_krw") is None]
    return covered, missing


def with_weights(accounts: list[dict]) -> list[dict]:
    """각 계좌에 weight_pct(전체 자산 대비 비중) 부여. 원본 accounts는 불변."""
    total = total_assets(accounts)
    if not total:
        return [{**a, "weight_pct": None} for a in accounts]
    return [
        {**a, "weight_pct": round(a["balance_krw"] / total * 100, 1) if a.get("balance_krw") is not None else None}
        for a in accounts
    ]


def goal_progress_pct(current: float | None, goal_amount: float | None) -> float | None:
    if not goal_amount or current is None:
        return None
    return round(current / goal_amount * 100, 1)


def with_holding_weights(holdings: list[dict]) -> list[dict]:
    """보유종목에 계좌 내 비중(weight_pct) 부여 — design/09 §3-4 비중 열·§3-5 비중 구성 카드.

    평가금액은 계좌 통화 기준(원화 계좌는 value_krw, 해외·코인은 value_usd)이지만 비중은
    같은 계좌 안의 비율이므로 통화 변환 없이 계산된다.
    """
    def _value(h: dict) -> float | None:
        return h.get("value_krw") if h.get("value_krw") is not None else h.get("value_usd")

    total = sum(v for h in holdings if (v := _value(h)) is not None)
    return [
        {**h, "weight_pct": round(_value(h) / total * 100, 1) if total and _value(h) is not None else None}
        for h in holdings
    ]


def total_pnl(accounts: list[dict]) -> tuple[float | None, float | None, float | None]:
    """(총수익, 총수익률%, 투입원금) — design/08 §3-2 Hero 3열.

    손익·원금을 모두 확보한 계좌만 합산한다. 하나도 없으면 (None, None, None)으로 생략한다
    (일부 계좌만 더한 '총수익'은 총수익이 아니다).
    """
    pairs = [
        (a["eval_pnl_krw"], a["principal_krw"]) for a in accounts
        if a.get("eval_pnl_krw") is not None and a.get("principal_krw") is not None
    ]
    if not pairs:
        return None, None, None
    pnl = round(sum(p for p, _ in pairs), 2)
    principal = round(sum(c for _, c in pairs), 2)
    return pnl, (round(pnl / principal * 100, 2) if principal else None), principal


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
