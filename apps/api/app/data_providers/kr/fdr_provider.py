"""FinanceDataReader 어댑터 (KR 우선). 무료·EOD(일봉). 라이브러리는 지연 임포트.

⚠️ 스크래핑 기반 비공식 소스 → 내부/PoC 한정. 실시간/주문은 KIS Developers로.
"""
from __future__ import annotations

import asyncio

from app.data_providers.base import QuoteProvider
from app.data_providers.errors import SourceUnavailable
from app.data_providers.normalization import InstrumentRef, now_utc, to_utc
from app.schemas.market import Candle, CandleSeries, ProviderMeta, Quote


def _bare_ticker(ref: InstrumentRef) -> str:
    """FDR은 접미사 없는 코드(005930)를 사용."""
    return ref.ticker.split(".")[0]


class FdrProvider(QuoteProvider):
    name = "fdr"
    tier = "free"
    markets = ("KR",)
    is_realtime = False
    priority = 40  # KR 기본(yfinance보다 우선)

    async def get_quote(self, ref: InstrumentRef) -> Quote:
        return await asyncio.to_thread(self._quote_sync, ref)

    def _quote_sync(self, ref: InstrumentRef) -> Quote:
        try:
            import FinanceDataReader as fdr

            df = fdr.DataReader(_bare_ticker(ref))
            if df is None or df.empty:
                raise SourceUnavailable(f"no data for {ref.ticker}")
            last = df.iloc[-1]
            price = float(last["Close"])
            change_pct = float(last["Change"]) * 100 if "Change" in df.columns else None
            volume = float(last["Volume"]) if "Volume" in df.columns else None
            return Quote(
                instrument_id=ref.instrument_id,
                symbol_norm=ref.symbol_norm,
                market=ref.market,
                currency=ref.currency,
                price=price,
                change_pct=round(change_pct, 4) if change_pct is not None else None,
                volume=volume,
                meta=ProviderMeta(
                    source=self.name, is_realtime=False, data_delay_sec=None, as_of=now_utc()
                ),
            )
        except SourceUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(f"fdr error: {exc}") from exc

    async def get_candles(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        return await asyncio.to_thread(self._candles_sync, ref, interval, frm, to)

    def _candles_sync(
        self, ref: InstrumentRef, interval: str, frm: str | None, to: str | None
    ) -> CandleSeries:
        # FDR은 기본 일봉. 분봉은 향후 KIS로 보강(여기선 1d만 지원).
        try:
            import FinanceDataReader as fdr

            df = fdr.DataReader(_bare_ticker(ref), frm, to)
            if df is None or df.empty:
                raise SourceUnavailable(f"no candles for {ref.ticker}")
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
                interval="1d",
                candles=candles,
                meta=ProviderMeta(
                    source=self.name, is_realtime=False, data_delay_sec=None, as_of=now_utc()
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise SourceUnavailable(f"fdr candles error: {exc}") from exc
