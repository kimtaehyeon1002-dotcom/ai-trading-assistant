"""ERP(자산/목표/워치리스트/현금흐름) 집계 — 순수 계산. 현재 실공급원은 vault(워치리스트)뿐이나
계약은 4개 DB 전체(자산/목표/워치리스트/현금흐름)를 지원한다(repositories.obsidian_repository 참고)."""
from __future__ import annotations


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) else 0.0


def summarize(erp: dict | None) -> dict | None:
    """정규화된 ERP → 대시보드 컨텍스트. 데이터 없으면 None(섹션 생략)."""
    if not erp:
        return None
    dbs = erp.get("databases", {})
    assets = dbs.get("assets", [])
    goals = dbs.get("goals", [])
    watchlist = dbs.get("watchlist", [])
    cashflow = dbs.get("cashflow", [])
    if not any((assets, goals, watchlist, cashflow)):
        return None

    by_type: dict[str, float] = {}
    for a in assets:
        t = a.get("유형") or "기타"
        by_type[t] = by_type.get(t, 0.0) + _num(a.get("금액"))

    goal_rows = []
    for g in goals:
        target, current = _num(g.get("목표금액")), _num(g.get("현재금액"))
        goal_rows.append(
            {
                "name": g.get("목표", ""),
                "target": target,
                "current": current,
                "progress_pct": round(current / target * 100, 1) if target > 0 else None,
                "due": g.get("기한", ""),
            }
        )

    recent_cash = sorted(cashflow, key=lambda c: c.get("날짜") or "", reverse=True)[:5]

    return {
        "as_of": erp.get("as_of", ""),
        "total_assets": round(sum(by_type.values()), 0),
        "assets_by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "goals": goal_rows,
        "watchlist": watchlist,
        "recent_cashflow": recent_cash,
    }
