from app.data_providers.normalization import market_for_symbol, normalize_symbol


def test_normalize_kr_kospi():
    assert normalize_symbol("KR", "005930") == "005930.KS"


def test_normalize_kr_kosdaq():
    assert normalize_symbol("KR", "035720", exchange="KOSDAQ") == "035720.KQ"


def test_normalize_us():
    assert normalize_symbol("US", "aapl") == "AAPL"


def test_market_for_symbol():
    assert market_for_symbol("005930.KS") == "KR"
    assert market_for_symbol("035720.KQ") == "KR"
    assert market_for_symbol("AAPL") == "US"
