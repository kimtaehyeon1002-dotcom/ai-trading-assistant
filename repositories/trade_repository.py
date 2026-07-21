"""매매 원장 — data/trades/trades.json ↔ Trade 모델. Kiwoom raw 변환도 여기서.

커밋되는 로컬 원장. GitHub Pages에는 쓰지 않는다(TH_DATA/10_Journal/trades/가 저널 발행 채널).
"""
from __future__ import annotations

from config.settings import TRADES_DIR
from models.trade import Trade
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("repositories.trade")
_STORE = TRADES_DIR / "trades.json"


def load_trades() -> list[Trade]:
    raw = load_json(_STORE, default=[])
    if not isinstance(raw, list):
        return []
    return [Trade.from_dict(d) for d in raw if isinstance(d, dict)]


def save_trades(trades: list[Trade]) -> None:
    trades = sorted(trades, key=lambda t: t.date, reverse=True)
    save_json(_STORE, [t.to_dict() for t in trades])


def _key(t: Trade) -> tuple:
    return (t.date, t.ticker, round(t.sell_price, 4), round(t.quantity, 4))


def add_trades(new: list[Trade]) -> list[Trade]:
    """신규 체결 dedup 병합 저장. 반환=전체 목록."""
    existing = load_trades()
    seen = {_key(t) for t in existing}
    added = 0
    for t in new:
        if _key(t) not in seen:
            existing.append(t)
            seen.add(_key(t))
            added += 1
    save_trades(existing)
    log.info("매매일지 추가 %d건 (총 %d건)", added, len(existing))
    return existing


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def add_from_kiwoom(raw_rows: list[dict], account_type: str = "위탁") -> list[Trade]:
    """Kiwoom 실현손익 raw(opt10073) → Trade 변환 후 원장 병합. broker='kiwoom' 고정(=단타)."""
    trades: list[Trade] = []
    skipped = 0
    for r in raw_rows:
        d = (r.get("일자") or "").replace("-", "")
        if len(d) != 8 or not r.get("종목코드"):  # 필드 미매칭/빈 행은 원장 오염 방지 차원에서 제외
            skipped += 1
            continue
        ymd = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        trades.append(
            Trade(
                date=ymd,
                ticker=(r.get("종목코드") or "").lstrip("A"),
                name=r.get("종목명", ""),
                buy_price=_num(r.get("매입단가")),
                sell_price=_num(r.get("체결단가")),
                quantity=_num(r.get("수량")),
                holding_days=int(_num(r.get("보유일수"))),
                account_type=account_type,
                broker="kiwoom",
            )
        )
    if skipped:
        log.warning("빈/미매칭 행 %d건 제외(필드명 확인 필요)", skipped)
    return add_trades(trades)
