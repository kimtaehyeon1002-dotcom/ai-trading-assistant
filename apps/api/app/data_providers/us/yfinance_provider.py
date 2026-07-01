"""yfinance 어댑터 (US 우선, KR 보조). 무료·지연 시세. 라이브러리는 지연 임포트.

⚠️ yfinance는 비공식이며 Yahoo ToS 위반 소지 → PoC/내부 한정. 고객대면·상업 재배포는 유료 소스로.
"""
from __future__ import annotations

import asyncio

from app.data_providers.base import QuoteProvider
from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import InstrumentRef, now_utc, to_utc
from app.schemas.market import Candle, CandleSeries, ProviderMeta, Quote

_INTERVAL_MAP = {"1m": "1m", "5m": "5m", "1h": "60m", "1d": "1d"}


class YFinanceProvider(QuoteProvider):
    name = "yfinance"
    tier = "free"
    markets = ("US", "KR")
    is_realtime = False
    priority = 50  # US 기본

    async def get_quote(self, ref: InstrumentRef) -> Quote:
        return await asyncio.to_thread(self._quote_sync, ref)

    def _quote_sync(self, ref: InstrumentRef) -> Quote:
        try:
            import yfinance as yf

            fi = yf.Ticker(ref.symbol_norm).fast_info
            price = fi.get("last_price") or fi.get("lastPrice")
            prev = fi.get("previous_close") or fi.get("previousClose")
            volume = fi.get("last_volume") or fi.get("lastVolume")
            if price is None:
                raise SourceUnavailable(f"no price for {ref.symbol_norm}")
            change_pct = round((price / prev - 1) * 100, 4) if prev else None
            return Quote(
                instrument_id=ref.instrument_id,
                symbol_norm=ref.symbol_norm,
                market=ref.market,
                currency=ref.currency,
                price=float(price),
                change_pct=change_pct,
                volume=float(volume) if volume is not None else None,
                meta=ProviderMeta(
                    source=self.name, is_realtime=False, data_delay_sec=900, as_of=now_utc()
                ),
            )
        except SourceUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - 외부 실패는 폴백 대상으로 정규화
            raise SourceUnavailable(f"yfinance error: {exc}") from exc

    async def get_candles(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        return await asyncio.to_thread(self._candles_sync, ref, interval, frm, to)

    def _candles_sync(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        try:
            import yfinance as yf

            yf_interval = _INTERVAL_MAP.get(interval, "1d")
            kwargs: dict = {"interval": yf_interval, "auto_adjust": False}
            if frm:
                kwargs["start"] = frm
            if to:
                kwargs["end"] = to
            if not frm and not to:
                kwargs["period"] = "6mo" if yf_interval == "1d" else "5d"
            df = yf.Ticker(ref.symbol_norm).history(**kwargs)
            candles = [
                Candle(
                    ts=to_utc(idx.to_pydatetime()),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    adjusted_close=float(row["Close"]),
                )
                for idx, row in df.iterrows()
            ]
            return CandleSeries(
                instrument_id=ref.instrument_id,
                symbol_norm=ref.symbol_norm,
                interval=interval,
                candles=candles,
                meta=ProviderMeta(
                    source=self.name, is_realtime=False, data_delay_sec=900, as_of=now_utc()
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(f"yfinance candles error: {exc}") from exc
