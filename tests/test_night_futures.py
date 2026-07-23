"""야간선물 수집 신뢰도 — 세션 창 판정 + 스킵 사유 기록(design/23 P2).

야간장은 자정을 넘는 유일한 세션(18:00~익일 05:00 KST)이라 "지금이 세션 중인가"를
단순 비교로 판정할 수 없다. 이 판정이 틀리면 마감 스냅샷(현재가=기준가)을 야간 시세로
착각해 저장하거나, 반대로 정상 시세를 버린다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.calendar import KR_NIGHT_CLOSE, KR_NIGHT_OPEN, is_kr_night_session

_KST = timezone(timedelta(hours=9))


def _at(hh: int, mm: int = 0) -> datetime:
    return datetime(2026, 7, 24, hh, mm, tzinfo=_KST)


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
