"""환율 어댑터(무료, yfinance FX 심볼). USDKRW=X 등. 향후 KIS/ECOS/ECB로 보강.

설계서 critique(§9-B)에서 누락 지적된 FX 소스를 Provider 인터페이스에 정식 등록.
"""
from __future__ import annotations

import asyncio

from app.data_providers.base import FxProvider
from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import now_utc
from app.schemas.market import FxRate, ProviderMeta


class YFinanceFxProvider(FxProvider):
    name = "yfinance_fx"
    tier = "free"
    markets = ("KR", "US")
    is_realtime = False
    priority = 60

    async def get_fx(self, base: str, quote: str) -> FxRate:
        return await asyncio.to_thread(self._fx_sync, base, quote)

    def _fx_sync(self, base: str, quote: str) -> FxRate:
        try:
            import yfinance as yf

            symbol = f"{base.upper()}{quote.upper()}=X"
            fi = yf.Ticker(symbol).fast_info
            rate = fi.get("last_price") or fi.get("lastPrice")
            if rate is None:
                raise SourceUnavailable(f"no fx for {symbol}")
            return FxRate(
                base=base.upper(),
                quote=quote.upper(),
                rate=float(rate),
                meta=ProviderMeta(
                    source=self.name, is_realtime=False, data_delay_sec=900, as_of=now_utc()
                ),
            )
        except SourceUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(f"yfinance fx error: {exc}") from exc
