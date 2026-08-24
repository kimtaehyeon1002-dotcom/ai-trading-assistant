"""랭킹 히스토리 원장(design/28 Phase A) — 기록 게이트·거래일·축소 스키마·롤링 보존.

이 원장은 소급 불가라서 "잘못 기록하는 것"이 "기록하지 않는 것"보다 나쁘다. 그래서 테스트의
무게중심도 저장 성공보다 **오염 차단**(장중 값이 완결된 거래일을 덮어쓰지 않는가)에 있다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from repositories import history_repository as hist

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(hist, "HISTORY_DIR", tmp_path / "rankings")
    return tmp_path / "rankings"


def _rows(n: int, base_amount: float = 1_000.0) -> list[dict]:
    return [
        {"code": f"{i:06d}", "name": f"종목{i}", "market": "KOSPI", "close": 100.0 + i,
         "change_pct": 1.5, "volume": 1_000 + i, "amount": base_amount - i, "marcap": 9.0}
        for i in range(n)
    ]


# ── 기록 게이트(KR) ────────────────────────────────────────────────────────

def test_kr_records_after_close_on_same_trade_date():
    now = datetime(2026, 8, 17, 15, 40, tzinfo=KST)
    assert hist.should_record_kr("2026-08-17", now=now) is True


def test_kr_skips_before_close():
    """장중 09:00 실행의 거래대금은 그날의 30분치일 뿐 — 결산이 아니다."""
    now = datetime(2026, 8, 17, 9, 0, tzinfo=KST)
    assert hist.should_record_kr("2026-08-17", now=now) is False


def test_kr_skips_when_trade_date_is_stale():
    """월요일 장중 시나리오 — KRX 스냅샷은 월요일 실시간인데 지수 일봉의 마지막은 금요일이다.

    시각 조건만 봤다면 월요일 값이 금요일 파일을 덮어써 완결된 원장을 오염시킨다.
    """
    now = datetime(2026, 8, 17, 16, 0, tzinfo=KST)  # 월 16:00, 마감은 지났다
    assert hist.should_record_kr("2026-08-14", now=now) is False


def test_kr_skips_without_trade_date():
    assert hist.should_record_kr(None, now=datetime(2026, 8, 17, 16, 0, tzinfo=KST)) is False


def test_kr_gate_open_is_time_only_precondition():
    assert hist.kr_gate_open(now=datetime(2026, 8, 17, 9, 0, tzinfo=KST)) is False
    assert hist.kr_gate_open(now=datetime(2026, 8, 17, 15, 35, tzinfo=KST)) is True


# ── 기록 게이트(US) ────────────────────────────────────────────────────────

def test_us_records_after_et_close_same_day():
    """UTC 22:00 크론 = ET 18:00(EDT) — 같은 날 마감 후."""
    now = datetime(2026, 8, 17, 22, 0, tzinfo=timezone.utc)
    assert hist.should_record_us("2026-08-17", now=now) is True


def test_us_records_when_trade_date_already_past():
    """KST 장중 실행은 ET로 전날 밤 — 이미 완결된 거래일이라 기록해도 안전하다."""
    now = datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)  # ET 8/17 23:00
    assert hist.should_record_us("2026-08-14", now=now) is True


def test_us_skips_during_regular_session():
    now = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)  # ET 11:00, 장중
    assert hist.should_record_us("2026-08-17", now=now) is False


# ── 기록 동작 ──────────────────────────────────────────────────────────────

def test_record_writes_file_named_by_trade_date(tmp_history):
    path = hist.record("kr", _rows(5), "2026-08-17")
    assert path == tmp_history / "kr" / "2026-08-17.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["trade_date"] == "2026-08-17"
    assert body["market"] == "kr"
    assert body["population"] == 5


def test_record_shrinks_to_top_n_with_short_keys():
    hist.HISTORY_TOP_N  # 계약 상수 존재 확인
    path = hist.record("kr", _rows(hist.HISTORY_TOP_N + 50), "2026-08-17")
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["population"] == hist.HISTORY_TOP_N + 50  # 모집단은 원본 크기
    assert len(body["rows"]) == hist.HISTORY_TOP_N        # 저장은 상위 N만
    assert set(body["rows"][0]) == {"c", "p", "r", "v", "a"}


def test_record_rounds_float_noise_away():
    """yfinance float64가 `123.45999908447266`으로 직렬화되는 것을 막는다 — 잡음이자 용량이다."""
    rows = [{"code": "TSLA", "close": 362.8599853515625, "change_pct": 5.1449,
             "volume": 58979800.0, "amount": 21401409364.038086}]
    body = json.loads(hist.record("us", rows, "2026-08-21").read_text(encoding="utf-8"))
    assert body["rows"][0] == {"c": "TSLA", "p": 362.86, "r": 5.14,
                               "v": 58979800, "a": 21401409364}


def test_record_stores_integral_prices_as_int():
    """KR 종가는 원 단위 정수 — `281500.0`의 `.0`이 300행 반복되면 그대로 용량이다."""
    rows = [{"code": "005930", "close": 281500.0, "change_pct": -1.0,
             "volume": 2737000, "amount": 770320000000.0}]
    body = json.loads(hist.record("kr", rows, "2026-08-21").read_text(encoding="utf-8"))
    assert body["rows"][0]["p"] == 281500
    assert '"p":281500,' in (hist.HISTORY_DIR / "kr" / "2026-08-21.json").read_text(encoding="utf-8")


def test_record_tolerates_missing_values():
    """US는 marcap이 없고 종목에 따라 change_pct도 결측이다 — None은 None으로 남는다."""
    rows = [{"code": "X", "close": 1.0, "change_pct": None, "volume": None, "amount": 5.0}]
    body = json.loads(hist.record("us", rows, "2026-08-21").read_text(encoding="utf-8"))
    assert body["rows"][0]["r"] is None and body["rows"][0]["v"] is None


def test_record_keeps_amount_descending_order():
    body = json.loads(hist.record("kr", _rows(10), "2026-08-17").read_text(encoding="utf-8"))
    amounts = [r["a"] for r in body["rows"]]
    assert amounts == sorted(amounts, reverse=True)


def test_record_skips_on_collection_failure(tmp_history):
    """수집 실패(None)로 빈 파일을 만들면 '데이터 없음'과 '거래 없음'을 구분할 수 없게 된다."""
    assert hist.record("kr", None, "2026-08-17") is None
    assert hist.record("kr", [], "2026-08-17") is None
    assert not (tmp_history / "kr").exists()


def test_record_skips_without_trade_date():
    assert hist.record("kr", _rows(3), None) is None


def test_record_is_compact(tmp_history):
    """indent=2로 저장하면 용량이 2~3배가 된다(design/28 §3-4)."""
    path = hist.record("kr", _rows(hist.HISTORY_TOP_N), "2026-08-17")
    text = path.read_text(encoding="utf-8")
    assert '": ' not in text  # compact separator
    assert path.stat().st_size < 20_000  # DoD 6: 파일당 20KB 이하


def test_markets_are_isolated(tmp_history):
    hist.record("kr", _rows(3), "2026-08-17")
    hist.record("us", _rows(3), "2026-08-17")
    assert (tmp_history / "kr" / "2026-08-17.json").exists()
    assert (tmp_history / "us" / "2026-08-17.json").exists()


# ── 보존 정책 ──────────────────────────────────────────────────────────────

def test_prune_drops_oldest_beyond_keep_limit(tmp_history, monkeypatch):
    monkeypatch.setattr(hist, "KEEP_FILES", 3)
    for day in range(1, 6):
        hist.record("kr", _rows(2), f"2026-08-{day:02d}")
    kept = sorted(p.stem for p in (tmp_history / "kr").glob("*.json"))
    assert kept == ["2026-08-03", "2026-08-04", "2026-08-05"]


def test_available_dates_is_sorted_and_safe_when_empty():
    assert hist.available_dates("kr") == []
    hist.record("kr", _rows(2), "2026-08-17")
    hist.record("kr", _rows(2), "2026-08-14")
    assert hist.available_dates("kr") == ["2026-08-14", "2026-08-17"]


def test_load_roundtrip_and_missing():
    hist.record("kr", _rows(2), "2026-08-17")
    assert hist.load("kr", "2026-08-17")["trade_date"] == "2026-08-17"
    assert hist.load("kr", "1999-01-01") is None


# ── 파이프라인 연결(design/28 Phase A DoD 1·3) ─────────────────────────────

def test_pipeline_records_only_when_gate_open(tmp_history, monkeypatch):
    """장중 실행은 거래일 확정 호출조차 하지 않는다 — 네트워크 1회를 아끼는 사전 조건(§3-1)."""
    from generators import pipelines

    calls = {"kr_trade_date": 0}

    def _kr_trade_date():
        calls["kr_trade_date"] += 1
        return "2026-08-17"

    monkeypatch.setattr(pipelines.krx_ranking_collector, "trade_date", _kr_trade_date)
    monkeypatch.setattr(pipelines.us_ranking_collector, "trade_date", lambda: None)
    monkeypatch.setattr(hist, "kr_gate_open", lambda now=None: False)

    pipelines._record_ranking_history(_rows(3), _rows(3))

    assert calls["kr_trade_date"] == 0
    assert not tmp_history.exists()


def test_pipeline_writes_both_markets_when_gates_pass(tmp_history, monkeypatch):
    from generators import pipelines

    monkeypatch.setattr(pipelines.krx_ranking_collector, "trade_date", lambda: "2026-08-17")
    monkeypatch.setattr(pipelines.us_ranking_collector, "trade_date", lambda: "2026-08-17")
    monkeypatch.setattr(hist, "kr_gate_open", lambda now=None: True)
    monkeypatch.setattr(hist, "should_record_kr", lambda d, now=None: True)
    monkeypatch.setattr(hist, "should_record_us", lambda d, now=None: True)

    pipelines._record_ranking_history(_rows(3), _rows(3))

    assert (tmp_history / "kr" / "2026-08-17.json").exists()
    assert (tmp_history / "us" / "2026-08-17.json").exists()


def test_pipeline_survives_collection_failure(tmp_history, monkeypatch):
    """수집이 실패해도 예외 없이 지나간다 — 히스토리는 발행을 막지 않는다."""
    from generators import pipelines

    monkeypatch.setattr(pipelines.krx_ranking_collector, "trade_date", lambda: None)
    monkeypatch.setattr(pipelines.us_ranking_collector, "trade_date", lambda: None)
    monkeypatch.setattr(hist, "kr_gate_open", lambda now=None: True)

    pipelines._record_ranking_history(None, None)

    assert not tmp_history.exists()
