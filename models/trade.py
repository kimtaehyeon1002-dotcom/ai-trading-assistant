"""매매 dataclass + 분류/통계(순수 로직, LLM 비의존)."""
from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import CLASSIFY

# 매매 카테고리
DAY = "day"
SWING = "swing"
LONG = "long"
CATEGORY_LABELS = {DAY: "단타", SWING: "스윙", LONG: "장기"}


def classify_category(holding_days: int) -> str:
    """보유일수 → 단타/스윙/장기 (기준: config.settings.CLASSIFY)."""
    if holding_days <= CLASSIFY["day_max_days"]:
        return DAY
    if holding_days <= CLASSIFY["swing_max_days"]:
        return SWING
    return LONG


@dataclass
class Trade:
    date: str  # 매도(청산)일 YYYY-MM-DD
    ticker: str
    name: str = ""
    buy_price: float = 0.0
    sell_price: float = 0.0
    quantity: float = 0.0
    holding_days: int = 0
    account_type: str = ""  # 위탁/CMA/ISA 등
    memo: str = ""
    category: str = ""  # 비면 holding_days로 자동 분류

    def __post_init__(self) -> None:
        if not self.category:
            self.category = classify_category(self.holding_days)

    @property
    def pnl(self) -> float:
        return round((self.sell_price - self.buy_price) * self.quantity, 2)

    @property
    def profit_pct(self) -> float | None:
        if not self.buy_price:
            return None
        return round((self.sell_price / self.buy_price - 1) * 100, 2)

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "ticker": self.ticker,
            "name": self.name,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "quantity": self.quantity,
            "holding_days": self.holding_days,
            "account_type": self.account_type,
            "memo": self.memo,
            "category": self.category,
            "pnl": self.pnl,
            "profit_pct": self.profit_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Trade":
        return cls(
            date=d.get("date", ""),
            ticker=d.get("ticker", ""),
            name=d.get("name", ""),
            buy_price=float(d.get("buy_price", 0) or 0),
            sell_price=float(d.get("sell_price", 0) or 0),
            quantity=float(d.get("quantity", 0) or 0),
            holding_days=int(d.get("holding_days", 0) or 0),
            account_type=d.get("account_type", ""),
            memo=d.get("memo", ""),
            category=d.get("category", ""),
        )


@dataclass
class TradeStats:
    n_trades: int = 0
    n_wins: int = 0
    n_losses: int = 0
    win_rate: float | None = None
    total_pnl: float = 0.0
    avg_profit: float | None = None  # 이긴 거래 평균
    avg_loss: float | None = None  # 진 거래 평균(음수)
    by_category: dict = field(default_factory=dict)  # {cat: {n, pnl, win_rate}}
    monthly: dict = field(default_factory=dict)  # {YYYY-MM: pnl}
