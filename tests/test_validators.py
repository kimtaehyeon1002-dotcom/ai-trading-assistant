from datetime import datetime, timedelta, timezone

from validators.market_validator import validate as v_market
from validators.news_validator import validate as v_news


def test_market_drops_invalid_price():
    raw = {
        "nasdaq": {"price": 26000.0, "change_pct": -0.5, "source": "yahoo"},
        "sp500": {"price": None, "source": "yahoo"},
        "dow": None,
        "wti": {"price": float("nan"), "source": "yahoo"},
        "usdkrw": {"price": -1, "source": "x"},
    }
    out = v_market(raw)
    assert out["nasdaq"] is not None
    assert out["sp500"] is None and out["dow"] is None
    assert out["wti"] is None and out["usdkrw"] is None  # NaN/음수 가격 거부


def test_market_night_futures_freshness():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=2)).isoformat()
    stale = (now - timedelta(hours=48)).isoformat()
    raw = {
        "kospi_night": {"price": 345.0, "as_of": fresh, "source": "kiwoom"},
        "kosdaq_night": {"price": 800.0, "as_of": stale, "source": "kiwoom"},
    }
    out = v_market(raw)
    assert out["kospi_night"] is not None
    assert out["kosdaq_night"] is None  # 만료 → 표시 금지


def test_news_requires_title_link_and_dedups():
    rows = [
        {"title": "A", "link": "http://x/1"},
        {"title": "", "link": "http://x/2"},
        {"title": "C", "link": ""},
        {"title": "A-dup", "link": "http://x/1"},
    ]
    out = v_news(rows)
    assert len(out) == 1 and out[0]["link"] == "http://x/1"


def test_news_future_timestamp_removed():
    future = datetime.now(timezone.utc) + timedelta(days=2)
    out = v_news([{"title": "T", "link": "http://x/9", "published": future}])
    assert out[0]["published"] is None
