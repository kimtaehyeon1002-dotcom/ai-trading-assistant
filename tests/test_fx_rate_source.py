"""USD/KRW 환율 소스 우선순위 — 자산 외화 환산의 정확도를 지키는 회귀(네트워크 미사용).

배경(실측 2026-08-02): 1순위가 Frankfurter(ECB 고시환율)여서 주말·공휴일에는 최대 3일 전
값이 쓰였다 — ECB 7/31자 1,443.61 vs 실시간 1,436.6으로 약 7원(0.5%) 차이. 자산 페이지의
한투 위탁·BYBIT 평가액이 이 환율로 환산되므로 그만큼 총자산이 틀어진다.

여기서는 (1) 실시간 소스가 먼저 시도되는지, (2) 실패 시 신선한 것부터 폴백하는지,
(3) 데스크톱(yfinance 미설치)에서도 실시간 경로가 성립하는지를 본다.
"""
from __future__ import annotations

from collectors import market_collector


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_YAHOO_OK = {"chart": {"result": [{"meta": {
    "regularMarketPrice": 1436.6,
    "chartPreviousClose": 1421.4,
    "regularMarketTime": 1785000000,
}}]}}

_ER_API_OK = {"rates": {"KRW": 1438.2}}
_ECB_OK = {"rates": {"KRW": 1443.61}, "date": "2026-07-31"}


def _route(monkeypatch, *, yahoo=None, er=None, ecb=None):
    """URL로 소스를 구분해 응답을 주입한다. None을 주면 그 소스는 실패로 만든다."""
    import requests

    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "query1.finance.yahoo.com" in url:
            if yahoo is None:
                raise OSError("yahoo down")
            return _Resp(yahoo)
        if "open.er-api.com" in url:
            if er is None:
                raise OSError("er-api down")
            return _Resp(er)
        if "frankfurter" in url:
            if ecb is None:
                raise OSError("ecb down")
            return _Resp(ecb)
        raise AssertionError(f"예상치 못한 URL: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


def test_live_fx_is_preferred_over_daily_fixing(monkeypatch):
    """★핵심: 실시간 시세가 있으면 ECB 고시환율을 쓰지 않는다."""
    calls = _route(monkeypatch, yahoo=_YAHOO_OK, er=_ER_API_OK, ecb=_ECB_OK)
    entry = market_collector._usdkrw()

    assert entry["price"] == 1436.6
    assert entry["source"] == "yahoo(fx-live)"
    assert all("frankfurter" not in c for c in calls), "실시간 성공 시 ECB를 호출하면 안 된다"


def test_live_fx_carries_quote_time(monkeypatch):
    """환산 근거 시각이 남아야 '언제 기준 환율인지'를 화면이 말할 수 있다."""
    _route(monkeypatch, yahoo=_YAHOO_OK)
    entry = market_collector._usdkrw()
    assert entry["as_of"].startswith("2026-")
    assert entry["change_pct"] == round((1436.6 / 1421.4 - 1) * 100, 2)


def test_falls_back_to_er_api_then_ecb(monkeypatch):
    """실시간 실패 시 더 자주 갱신되는 소스부터 내려간다(ECB가 마지막)."""
    _route(monkeypatch, yahoo=None, er=_ER_API_OK, ecb=_ECB_OK)
    assert market_collector._usdkrw()["price"] == 1438.2

    _route(monkeypatch, yahoo=None, er=None, ecb=_ECB_OK)
    entry = market_collector._usdkrw()
    assert entry["price"] == 1443.61
    assert "2026-07-31" in entry["source"], "고시일을 소스에 남겨 낡음을 추적할 수 있어야 한다"


def test_returns_none_when_every_source_fails(monkeypatch):
    """전부 실패하면 결측 — 옛 환율을 만들어 쓰지 않는다(가짜 데이터 금지)."""
    _route(monkeypatch, yahoo=None, er=None, ecb=None)
    assert market_collector._usdkrw() is None


def test_live_path_does_not_require_yfinance(monkeypatch):
    """데스크톱(.venv32)엔 yfinance가 없다 — 그 경로에 의존하면 자산 빌드에서 무용지물이다."""
    monkeypatch.setattr(market_collector, "_yahoo_available", lambda: False)
    _route(monkeypatch, yahoo=_YAHOO_OK)
    assert market_collector._usdkrw()["source"] == "yahoo(fx-live)"
