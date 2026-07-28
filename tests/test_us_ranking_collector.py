"""us_ranking_collector.collect_quotes — 거래량 0을 결측(None)과 구분하는지 검증."""
from __future__ import annotations

import pandas as pd

from collectors import us_ranking_collector


def _fake_download(tickers=None, period=None, group_by=None, threads=None, progress=None):
    df = pd.DataFrame({
        ("AAA", "Close"): [10.0, 11.0],
        ("AAA", "Volume"): [100, 0],
    })
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


def test_zero_volume_gives_zero_amount_not_close(monkeypatch):
    """★회귀: `if volume else close`는 volume==0(거래정지·데이터 공백)을
    volume 결측(None)과 똑같이 취급해 거래대금을 종가로 날조했다."""
    monkeypatch.setattr("yfinance.download", _fake_download)
    out = us_ranking_collector.collect_quotes(["AAA"])
    assert out["AAA"]["volume"] == 0
    assert out["AAA"]["amount"] == 0
