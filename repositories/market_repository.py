"""검증된 시장 raw → Quote 모델 + cache/market.json 기록."""
from __future__ import annotations

from datetime import datetime

from collectors.kiwoom_collector import LABELS as NIGHT_LABELS
from config.markets import MORNING_US_INDICES
from config.settings import CACHE_DIR
from models.market import Quote
from utils.dates import fmt_kst, now_kst
from utils.jsonio import save_json


def _as_of_kst(iso: str) -> str:
    """ISO 타임스탬프 → 'MM-DD HH:MM' KST 표시 문자열(파싱 실패 시 빈 문자열)."""
    try:
        return fmt_kst(datetime.fromisoformat(iso), "%m-%d %H:%M")
    except (ValueError, TypeError):
        return ""

_NAMES = {
    **NIGHT_LABELS,
    "usdkrw": "USD/KRW 환율",
    "wti": "WTI 국제유가",
    **{key: label for key, _sym, label in MORNING_US_INDICES},
}
_CURRENCY = {"usdkrw": "KRW", "kospi_night": "KRW", "kosdaq_night": "KRW"}


def to_quotes(validated: dict[str, dict | None]) -> dict[str, Quote | None]:
    out: dict[str, Quote | None] = {}
    for key, e in validated.items():
        if e is None:
            out[key] = None
            continue
        out[key] = Quote(
            symbol=key,
            name=_NAMES.get(key, key),
            price=e["price"],
            change_pct=e.get("change_pct"),
            currency=_CURRENCY.get(key, "USD"),
            source=e.get("source", ""),
            as_of=_as_of_kst(e.get("as_of", "")),
        )
    return out


def persist(quotes: dict[str, Quote | None]) -> None:
    save_json(
        CACHE_DIR / "market.json",
        {
            "as_of": now_kst().isoformat(),
            **{
                k: (
                    {"name": q.name, "price": q.price, "change_pct": q.change_pct, "source": q.source}
                    if q
                    else None
                )
                for k, q in quotes.items()
            },
        },
    )
