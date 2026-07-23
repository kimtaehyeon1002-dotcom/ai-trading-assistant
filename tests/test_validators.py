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


# ---------- 야간선물 표시 만료: 평일 20h / 주말 경유 60h(design/23 P2) ----------
# 시각은 전부 KST로 고정 주입한다 — 주말 규칙이 있어 "실행 시점의 요일"에 결과가 달라지면
# 테스트가 요일 따라 깜빡인다(2026-07-22=수, 07-24=금, 07-18=토, 07-20=월).

_KST = timezone(timedelta(hours=9))


def _night(as_of: datetime, change_pct: float = -0.4) -> dict:
    return {"price": 345.0, "change_pct": change_pct,
            "as_of": as_of.isoformat(), "source": "kiwoom"}


def test_night_futures_kept_same_morning():
    """정상 경로 — 새벽 수집분이 같은 날 아침 리포트에 실린다(1.8h)."""
    out = v_market({"kospi_night": _night(datetime(2026, 7, 24, 4, 40, tzinfo=_KST))},
                   now=datetime(2026, 7, 24, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is not None


def test_night_futures_kept_from_session_open():
    """세션 개시(18:00) 직후 수집분이 다음 날 아침에 실리는 경우가 평일 최장(12.5h)."""
    out = v_market({"kospi_night": _night(datetime(2026, 7, 23, 18, 5, tzinfo=_KST))},
                   now=datetime(2026, 7, 24, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is not None


def test_night_futures_drops_previous_session_on_weekday():
    """한 세션 낡은 값(어제 새벽, 25.8h)은 평일 한도 20h를 넘어 탈락한다."""
    out = v_market({"kospi_night": _night(datetime(2026, 7, 23, 4, 40, tzinfo=_KST))},
                   now=datetime(2026, 7, 24, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is None


def test_night_futures_drops_two_day_old_weekday_regression():
    """실제 사고 재현(design/23 P2): 수요일 밤 23:12 값이 금요일 06:04 리포트에 생존했다.

    31h · 구간에 주말 없음 → 탈락해야 한다(종전 60h 단일 한도에서는 통과했다).
    """
    out = v_market({"kospi_night": _night(datetime(2026, 7, 22, 23, 12, tzinfo=_KST), -0.06)},
                   now=datetime(2026, 7, 24, 6, 4, tzinfo=_KST))
    assert out["kospi_night"] is None


def test_night_futures_kept_over_weekend():
    """금요일 밤 세션(토 04:40 수집) 값은 월요일 아침 리포트까지 살아야 한다(49.8h)."""
    out = v_market({"kospi_night": _night(datetime(2026, 7, 18, 4, 40, tzinfo=_KST))},
                   now=datetime(2026, 7, 20, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is not None


def test_night_futures_drops_beyond_weekend_cap():
    """목요일 밤 세션(금 04:40) 값은 월요일 아침엔 73.8h — 주말 한도 60h도 넘어 탈락."""
    out = v_market({"kospi_night": _night(datetime(2026, 7, 17, 4, 40, tzinfo=_KST))},
                   now=datetime(2026, 7, 20, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is None


def test_night_futures_requires_as_of():
    """타임스탬프 없는 값은 나이를 알 수 없다 → 표시 금지."""
    out = v_market({"kospi_night": {"price": 345.0, "change_pct": -0.4, "source": "kiwoom"}},
                   now=datetime(2026, 7, 24, 6, 30, tzinfo=_KST))
    assert out["kospi_night"] is None


def test_market_night_futures_drops_flat():
    """등락 0.0/누락 야간선물 = 마감·개장전 스냅샷 → 표시 금지(현물과 어긋난 stale 값 차단)."""
    now = datetime.now(timezone.utc).isoformat()
    raw = {
        "kospi_night": {"price": 1304.0, "change_pct": 0.0, "as_of": now, "source": "kiwoom"},
        "kosdaq_night": {"price": 1490.0, "as_of": now, "source": "kiwoom"},  # change_pct 누락
    }
    out = v_market(raw)
    assert out["kospi_night"] is None and out["kosdaq_night"] is None


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
