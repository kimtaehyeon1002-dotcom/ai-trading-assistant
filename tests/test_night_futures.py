"""야간선물 수집 신뢰도 — 세션 창 판정 + 스킵 사유 기록(design/23 P2).

야간장은 자정을 넘는 유일한 세션(18:00~익일 05:00 KST)이라 "지금이 세션 중인가"를
단순 비교로 판정할 수 없다. 이 판정이 틀리면 마감 스냅샷(현재가=기준가)을 야간 시세로
착각해 저장하거나, 반대로 정상 시세를 버린다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.calendar import (
    KR_FUTURES_REGULAR_CLOSE,
    KR_NIGHT_CLOSE,
    KR_NIGHT_OPEN,
    is_kr_futures_close_window,
    is_kr_night_session,
    night_base_trading_day,
)
from config.markets import BASE_DAY_CLOSE, BASE_PREV_CLOSE

_KST = timezone(timedelta(hours=9))


def _at(hh: int, mm: int = 0, day: int = 24) -> datetime:
    return datetime(2026, 7, day, hh, mm, tzinfo=_KST)


# ---------- 세션 창 판정(자정 넘김) ----------

def test_night_session_window_boundaries():
    assert KR_NIGHT_OPEN == "18:00" and KR_NIGHT_CLOSE == "05:00"
    assert is_kr_night_session(_at(18, 0))       # 개시 시각 포함
    assert is_kr_night_session(_at(23, 59))      # 자정 직전
    assert is_kr_night_session(_at(0, 0))        # 자정 직후 — 같은 세션의 연속
    assert is_kr_night_session(_at(4, 59))       # 마감 직전
    assert not is_kr_night_session(_at(5, 0))    # 마감 시각은 세션 밖
    assert not is_kr_night_session(_at(17, 59))  # 개시 직전


def test_night_session_excludes_report_and_regular_hours():
    """실제 사고 시각(06:04)과 정규장 시간대는 세션 밖으로 판정돼야 한다.

    06:04 조회가 세션 중으로 오판되면 flat 스냅샷이 그대로 저장되어, 밤사이 등락이
    0.00%로 덮인다(design/23 P2에서 확인된 경로).
    """
    assert not is_kr_night_session(_at(6, 4))    # 종전 자동 동기화가 돌던 시각
    assert not is_kr_night_session(_at(9, 0))    # 정규장 개장
    assert not is_kr_night_session(_at(15, 30))  # 정규장 마감


# ---------- 스킵 사유 기록(값은 보존) ----------

def test_save_skip_reason_preserves_last_quote(tmp_path, monkeypatch):
    from collectors import kiwoom_collector

    monkeypatch.setattr(kiwoom_collector, "_CACHE", tmp_path / "kiwoom_night.json")
    kiwoom_collector.save_night_futures(kospi={"price": 1132.5, "change_pct": 1.7})
    kiwoom_collector.save_skip_reason("야간 세션 아님(현재 06:04)")

    out = kiwoom_collector.collect()
    assert out["kospi_night"]["price"] == 1132.5  # 스킵이 직전 값을 덮지 않는다
    assert out["kospi_night"]["change_pct"] == 1.7


def test_skip_reason_cleared_on_successful_update(tmp_path, monkeypatch):
    from collectors import kiwoom_collector
    from utils.jsonio import load_json

    cache = tmp_path / "kiwoom_night.json"
    monkeypatch.setattr(kiwoom_collector, "_CACHE", cache)
    kiwoom_collector.save_skip_reason("야간 세션 아님(현재 06:04)")
    assert load_json(cache, default={})["last_skip"]["reason"]

    kiwoom_collector.save_night_futures(kospi={"price": 1132.5, "change_pct": 1.7})
    assert "last_skip" not in load_json(cache, default={})  # 해소된 사유는 남기지 않는다


def test_skip_reason_is_not_mistaken_for_a_quote(tmp_path, monkeypatch):
    """캐시에 섞인 메타 키가 시세로 새어나가면 안 된다(collect는 야간선물 2종만 반환)."""
    from collectors import kiwoom_collector

    monkeypatch.setattr(kiwoom_collector, "_CACHE", tmp_path / "kiwoom_night.json")
    kiwoom_collector.save_skip_reason("세션 아님")
    assert set(kiwoom_collector.collect()) == {"kospi_night", "kosdaq_night"}
    assert kiwoom_collector.collect()["kospi_night"] is None


# ---------- 등락 기준 = 직전 정규장 종가(design/27) ----------

def test_futures_close_window_boundaries():
    """종가 확정 창은 선물 마감(15:45)부터 야간 개시(18:00)까지 — 현물 마감(15:30)이 아니다."""
    assert KR_FUTURES_REGULAR_CLOSE == "15:45"
    assert not is_kr_futures_close_window(_at(15, 30))  # 현물은 마감했지만 선물은 아직 장중
    assert not is_kr_futures_close_window(_at(15, 44))
    assert is_kr_futures_close_window(_at(15, 45))      # 마감 시각 = 종가 확정
    assert is_kr_futures_close_window(_at(17, 59))
    assert not is_kr_futures_close_window(_at(18, 0))   # 야간 개시 = 이미 야간 체결가
    assert not is_kr_futures_close_window(_at(9, 0))


def test_close_window_and_night_session_never_overlap():
    """두 창이 겹치면 같은 시세를 '종가'이자 '야간가'로 이중 해석하게 된다."""
    for hh in range(24):
        for mm in (0, 30, 44, 45, 59):
            t = _at(hh, mm)
            assert not (is_kr_futures_close_window(t) and is_kr_night_session(t))


def test_night_base_trading_day_survives_midnight():
    """07-30 22:30과 07-31 00:02는 같은 세션 — 기준 거래일은 둘 다 07-30이어야 한다.

    이 대응이 하루 어긋나면 07-29 종가를 기준으로 잡아 07-30 주간 하락분이 야간 등락률에
    통째로 섞인다(2026-07-31 실제 오독: 야간선물 -3.46%로 표시, 실제 밤사이는 -2.25%).
    """
    assert night_base_trading_day(_at(18, 0, day=30)).isoformat() == "2026-07-30"
    assert night_base_trading_day(_at(22, 30, day=30)).isoformat() == "2026-07-30"
    assert night_base_trading_day(_at(0, 2, day=31)).isoformat() == "2026-07-30"
    assert night_base_trading_day(_at(4, 59, day=31)).isoformat() == "2026-07-30"


def test_rebase_strips_daytime_move():
    """실측 재현(2026-07-30 야간): 기준가 898.65(07-29 종가) → 종가 887.60(07-30) 기준 환산."""
    from collectors.kiwoom_desktop import futures

    leg = {"price": 867.6, "change_pct": -3.46, "ref_price": 898.65,
           "base_kind": BASE_PREV_CLOSE}
    out = futures.rebase_to_day_close(leg, 887.60)
    assert out["change_pct"] == -2.25       # 주간 하락분(-1.2%p)이 걷혔다
    assert out["ref_price"] == 887.60
    assert out["base_kind"] == BASE_DAY_CLOSE
    assert out["price"] == 867.6            # 가격은 건드리지 않는다


def test_rebase_falls_back_without_day_close():
    """종가 미확보 시 값을 지어내지 않고 기준가 대비를 그대로 유지한다(기준은 정직하게 표기)."""
    from collectors.kiwoom_desktop import futures

    leg = {"price": 867.6, "change_pct": -3.46, "ref_price": 898.65,
           "base_kind": BASE_PREV_CLOSE}
    for bad in (None, 0, -1):
        out = futures.rebase_to_day_close(leg, bad)
        assert out["change_pct"] == -3.46 and out["base_kind"] == BASE_PREV_CLOSE


def test_day_close_requires_matching_trading_day(tmp_path, monkeypatch):
    """거래일이 어긋난 종가는 쓰지 않는다 — 그게 애초에 고치려던 '하루 밀린 기준가'다."""
    from collectors import kiwoom_collector

    monkeypatch.setattr(kiwoom_collector, "_CACHE", tmp_path / "kiwoom_night.json")
    kiwoom_collector.save_day_close("2026-07-30", {"kospi_night": 887.6, "kosdaq_night": 1100.0})

    assert kiwoom_collector.load_day_close("2026-07-30")["kospi_night"] == 887.6
    assert kiwoom_collector.load_day_close("2026-07-29") == {}  # 수집을 거른 날 → 폴백
    assert kiwoom_collector.load_day_close("2026-07-31") == {}


def test_day_close_and_night_quote_coexist(tmp_path, monkeypatch):
    """같은 캐시 파일을 쓰지만 서로를 덮지 않는다(종가 저장 → 야간 저장 → 둘 다 살아있다)."""
    from collectors import kiwoom_collector

    monkeypatch.setattr(kiwoom_collector, "_CACHE", tmp_path / "kiwoom_night.json")
    kiwoom_collector.save_day_close("2026-07-30", {"kospi_night": 887.6})
    kiwoom_collector.save_night_futures(
        kospi={"price": 867.6, "change_pct": -2.25, "ref_price": 887.6,
               "base_kind": BASE_DAY_CLOSE}
    )

    assert kiwoom_collector.load_day_close("2026-07-30")["kospi_night"] == 887.6
    quote = kiwoom_collector.collect()["kospi_night"]
    assert quote["change_pct"] == -2.25
    assert quote["base_kind"] == BASE_DAY_CLOSE  # 기준 메타가 캐시를 통과해 표시단까지 간다
    assert set(kiwoom_collector.collect()) == {"kospi_night", "kosdaq_night"}  # day_close 미유출


# ---------- 표시단 고지 ----------

def _night_quotes(*kinds: str | None):
    from repositories.market_repository import to_quotes

    raw = {key: {"price": 900.0, "change_pct": -1.0, "source": "kiwoom", "base_kind": kind}
           for key, kind in zip(("kospi_night", "kosdaq_night"), kinds)}
    return to_quotes(raw)


def test_basis_note_reflects_actual_basis():
    from config.markets import NIGHT_BASIS_NOTE
    from repositories.market_repository import night_basis_note

    assert night_basis_note(_night_quotes(BASE_DAY_CLOSE, BASE_DAY_CLOSE)) == \
        NIGHT_BASIS_NOTE[BASE_DAY_CLOSE]
    assert night_basis_note(_night_quotes(BASE_PREV_CLOSE, BASE_PREV_CLOSE)) == \
        NIGHT_BASIS_NOTE[BASE_PREV_CLOSE]


def test_basis_note_downgrades_when_two_tiles_disagree():
    """한쪽만 종가를 확보했는데 '밤사이 변동분'이라 단언하면 나머지 타일을 잘못 읽게 된다."""
    from config.markets import NIGHT_BASIS_NOTE
    from repositories.market_repository import night_basis_note

    assert night_basis_note(_night_quotes(BASE_DAY_CLOSE, BASE_PREV_CLOSE)) == \
        NIGHT_BASIS_NOTE[BASE_PREV_CLOSE]


def test_basis_note_absent_without_night_futures():
    """야간선물이 없으면 고지도 없다 — 빈 문구 행을 만들지 않는다(팩트 우선)."""
    from repositories.market_repository import night_basis_note

    assert night_basis_note({"kospi_night": None, "kosdaq_night": None}) is None
    assert night_basis_note({}) is None


# ---------- 수집 경로 전체(창 판정 → 종가 저장 → 야간 환산) ----------

def _run_sync_at(monkeypatch, tmp_path, when: datetime, prices: dict[str, float]):
    """_sync_index_futures를 고정 시각·고정 시세로 1회 실행하고 캐시 파일을 남긴다."""
    from app import sync
    from collectors import kiwoom_collector
    from collectors.kiwoom_desktop import futures

    monkeypatch.setattr(kiwoom_collector, "_CACHE", tmp_path / "kiwoom_night.json")
    monkeypatch.setattr(futures, "now_kst", lambda: when)
    monkeypatch.setattr("utils.dates.now_kst", lambda: when)
    # 기준가는 실측 그대로 '하루 밀린' 값(07-29 종가)을 준다 — 폴백 경로가 무엇을 재는지 드러난다.
    monkeypatch.setattr(futures, "fetch_front_month_quotes", lambda _api: {
        key: {"price": p, "change_pct": round((p / 898.65 - 1) * 100, 2),
              "ref_price": 898.65, "base_kind": BASE_PREV_CLOSE}
        for key, p in prices.items()
    })
    sync._sync_index_futures(object())


def test_close_window_run_records_base_and_leaves_quotes_untouched(monkeypatch, tmp_path):
    from collectors import kiwoom_collector

    _run_sync_at(monkeypatch, tmp_path, _at(15, 50, day=30), {"kospi_night": 887.6})

    assert kiwoom_collector.load_day_close("2026-07-30") == {"kospi_night": 887.6}
    # 종가 확정 실행이 야간 시세 슬롯을 건드리면 마감값이 '야간 시세'로 둔갑한다.
    assert kiwoom_collector.collect()["kospi_night"] is None


def test_night_run_rebases_onto_same_day_close(monkeypatch, tmp_path):
    """07-30 15:50 종가 확정 → 07-31 00:02 야간 수집. 자정을 넘어도 같은 거래일로 묶인다."""
    from collectors import kiwoom_collector

    _run_sync_at(monkeypatch, tmp_path, _at(15, 50, day=30), {"kospi_night": 887.6})
    _run_sync_at(monkeypatch, tmp_path, _at(0, 2, day=31), {"kospi_night": 867.6})

    quote = kiwoom_collector.collect()["kospi_night"]
    assert quote["change_pct"] == -2.25          # 기준가 폴백이면 -3.46이 나온다
    assert quote["base_kind"] == BASE_DAY_CLOSE
    assert quote["ref_price"] == 887.6


def test_night_run_without_close_capture_falls_back_honestly(monkeypatch, tmp_path):
    """종가 확정 실행을 걸렀을 때 — 값은 나오되 기준이 폴백임을 표기한다."""
    from collectors import kiwoom_collector

    _run_sync_at(monkeypatch, tmp_path, _at(0, 2, day=31), {"kospi_night": 867.6})

    quote = kiwoom_collector.collect()["kospi_night"]
    assert quote["change_pct"] == -3.46
    assert quote["base_kind"] == BASE_PREV_CLOSE


def test_stale_day_close_is_not_reused_next_night(monkeypatch, tmp_path):
    """07-30 종가가 캐시에 남아 있어도 07-31 밤의 기준으로 쓰지 않는다(하루 밀림 재발 방지)."""
    from collectors import kiwoom_collector

    _run_sync_at(monkeypatch, tmp_path, _at(15, 50, day=30), {"kospi_night": 887.6})
    _run_sync_at(monkeypatch, tmp_path, _at(22, 30, day=31), {"kospi_night": 867.6})

    assert kiwoom_collector.collect()["kospi_night"]["base_kind"] == BASE_PREV_CLOSE


def test_outside_both_windows_records_skip_and_keeps_last_quote(monkeypatch, tmp_path):
    """정규장 중(11:00) 실행은 아무것도 수집하지 않는다 — flat 스냅샷 저장이 P2의 원인이었다."""
    from collectors import kiwoom_collector
    from utils.jsonio import load_json

    _run_sync_at(monkeypatch, tmp_path, _at(15, 50, day=30), {"kospi_night": 887.6})
    _run_sync_at(monkeypatch, tmp_path, _at(0, 2, day=31), {"kospi_night": 867.6})
    _run_sync_at(monkeypatch, tmp_path, _at(11, 0, day=31), {"kospi_night": 999.9})

    quote = kiwoom_collector.collect()["kospi_night"]
    assert quote["price"] == 867.6 and quote["change_pct"] == -2.25  # 직전 야간 값 보존
    assert load_json(tmp_path / "kiwoom_night.json", default={})["last_skip"]["reason"]
