"""루프 센서 검증(design/26 Phase A DoD) — 규칙별 정탐 + **정상 상태에서 오탐 0**.

오탐 0이 이 루프의 생사를 가른다: 센서가 한 번이라도 거짓 위반을 내면 그 위에 얹는
자동수정은 멀쩡한 코드를 고치기 시작한다. 그래서 "모든 워커가 건강한 runlog"를 합성해
위반이 정확히 0건인지 먼저 확인한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config import slo
from config.settings import TIMEZONE
from scripts.health_probe import _slug, check_workers, probe
from utils import runlog
from utils.jsonio import save_json

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=TIMEZONE)  # 수요일 정오


def _healthy(now: datetime = NOW) -> dict:
    """선언된 전 워커가 방금 정상 실행된 runlog 워커 블록."""
    return {
        name: {
            "worker": name,
            "status": spec.status_ok[0],
            "last_run": (now - timedelta(minutes=1)).isoformat(),
            "items": spec.min_items if spec.min_items is not None else 1,
            "duration_ms": 10,
        }
        for name, spec in slo.WORKERS.items()
    }


def test_healthy_runlog_has_no_violations():
    assert check_workers(_healthy(), NOW) == []


def test_declared_worker_missing_from_runlog():
    workers = _healthy()
    workers.pop("Macro FRED")
    ids = [v["id"] for v in check_workers(workers, NOW)]
    assert "w.macro-fred.missing" in ids


def test_error_status_is_critical():
    workers = _healthy()
    workers["News Research"] |= {"status": "error", "last_error": "RSS timeout"}
    v = next(v for v in check_workers(workers, NOW) if v["id"] == "w.news-research.status")
    assert v["severity"] == "critical"
    assert "RSS timeout" in v["observed"]


def test_skipped_is_normal_only_where_declared():
    """같은 skipped라도 워커에 따라 정상/위반이 갈린다 — status_ok 선언이 유일한 기준."""
    workers = _healthy()
    workers["Vault Sync"] |= {"status": "skipped"}      # 허용 선언됨
    workers["Macro Upbit"] |= {"status": "skipped"}     # 허용 선언 없음
    ids = [v["id"] for v in check_workers(workers, NOW)]
    assert "w.vault-sync.status" not in ids
    assert "w.macro-upbit.status" in ids


def test_stale_worker_detected_on_weekday():
    workers = _healthy()
    workers["Macro FRED"] |= {"last_run": (NOW - timedelta(hours=5)).isoformat()}
    v = next(v for v in check_workers(workers, NOW) if v["id"] == "w.macro-fred.stale")
    assert v["severity"] == "major"


def test_weekend_gap_is_not_stale():
    """금요일 06:30 실행 → 월요일 06:00 시점(71.5h)은 주말 상한(76h) 안이라 정상이다.

    TA Analyst는 morning.yml(06:30 KST 월~금) 전용이라 금→월 공백이 정상 운영이다.
    """
    friday = datetime(2026, 7, 24, 6, 30, tzinfo=TIMEZONE)
    monday = datetime(2026, 7, 27, 6, 0, tzinfo=TIMEZONE)
    workers = _healthy(monday)
    workers["TA Analyst"] |= {"last_run": friday.isoformat()}
    assert [v for v in check_workers(workers, monday) if v["id"] == "w.ta-analyst.stale"] == []


def test_weekday_gap_beyond_limit_is_stale_even_though_weekend_rule_exists():
    """주말 상한이 있는 워커라도 평일 구간이면 평일 상한(26h)으로 판정한다."""
    tuesday = datetime(2026, 7, 28, 6, 0, tzinfo=TIMEZONE)
    wednesday = datetime(2026, 7, 29, 12, 0, tzinfo=TIMEZONE)  # 30h 후, 주말 없음
    workers = _healthy(wednesday)
    workers["TA Analyst"] |= {"last_run": tuesday.isoformat()}
    ids = [v["id"] for v in check_workers(workers, wednesday)]
    assert "w.ta-analyst.stale" in ids


def test_on_demand_worker_is_never_stale():
    """Trade Manager는 push 트리거 전용 — 몇 주 안 돌아도 정상이다."""
    workers = _healthy()
    workers["Trade Manager"] |= {"last_run": (NOW - timedelta(days=30)).isoformat()}
    assert [v for v in check_workers(workers, NOW) if v["subject"] == "Trade Manager"] == []


def test_silent_zero_collection_caught_by_min_items():
    workers = _healthy()
    workers["Stock KR Ranking"] |= {"status": "completed", "items": 0}
    v = next(v for v in check_workers(workers, NOW) if v["id"] == "w.stock-kr-ranking.items")
    assert "0건" in v["observed"]


def test_undeclared_worker_is_minor():
    workers = _healthy()
    workers["Brand New Worker"] = {"status": "completed", "last_run": NOW.isoformat()}
    v = next(v for v in check_workers(workers, NOW) if v["rule"] == "SLO 등재")
    assert v["severity"] == "minor"


def test_desktop_tier_is_labelled():
    """클라우드 루틴이 절대 손대면 안 되는 위반은 tier로 구분돼야 한다(design/26 §3-7)."""
    workers = _healthy()
    workers["Asset Kiwoom"] |= {"status": "error", "last_error": "OCX 연결 실패"}
    v = next(v for v in check_workers(workers, NOW) if v["id"] == "w.asset-kiwoom.status")
    assert v["tier"] == slo.TIER_DESKTOP


@pytest.mark.parametrize("name", list(slo.WORKERS))
def test_slug_is_branch_safe_and_unique(name):
    """이슈 id는 `fix/<id>` 브랜치명이 된다 — ascii + 유일해야 한다."""
    s = _slug(name)
    assert s and s.isascii() and " " not in s
    assert len({_slug(n) for n in slo.WORKERS}) == len(slo.WORKERS)


def test_probe_reports_missing_runlog_honestly(tmp_path):
    """runlog가 없으면 '위반 0'이 아니라 소스 결손을 사실대로 알려야 한다."""
    result = probe(runlog_path=tmp_path / "none.json", now=NOW, with_workflows=False)
    assert result["sources"]["runlog"].startswith("missing")
    assert result["counts"]["major"] == len(slo.WORKERS)  # 전 워커가 missing


def test_probe_output_is_sorted_by_severity(tmp_path):
    workers = _healthy()
    workers["News Research"] |= {"status": "error"}
    workers["Brand New Worker"] = {"status": "completed", "last_run": NOW.isoformat()}
    path = tmp_path / "runlog.json"
    save_json(path, {"updated_at": NOW.isoformat(), "workers": workers})

    result = probe(runlog_path=path, now=NOW, with_workflows=False)
    severities = [v["severity"] for v in result["violations"]]
    assert severities == sorted(severities, key=slo.SEVERITY_ORDER.index)


# ── runlog 공유 원장 병합(2026-07-28 기록 유실 사고) ──────────────────────────


def test_merge_restores_records_only_the_remote_has():
    remote = {"FS DART corpCode": {"status": "completed", "last_run": "2026-07-27T06:00:00+09:00"}}
    local = {"Asset Kiwoom": {"status": "completed", "last_run": "2026-07-28T07:49:00+09:00"}}
    merged = runlog.merge_by_recency(remote, local)
    assert set(merged) == {"FS DART corpCode", "Asset Kiwoom"}


def test_merge_does_not_regress_a_newer_remote_record():
    """데스크톱 로컬 사본의 낡은 기록이 원격 최신 기록을 덮으면 가짜 stale이 생긴다."""
    remote = {"Macro FRED": {"status": "completed", "last_run": "2026-07-29T11:00:00+09:00"}}
    local = {"Macro FRED": {"status": "completed", "last_run": "2026-07-26T09:00:00+09:00"}}
    assert runlog.merge_by_recency(remote, local)["Macro FRED"]["last_run"].startswith("2026-07-29")


def test_merge_tolerates_broken_timestamps():
    remote = {"X": {"status": "completed", "last_run": "2026-07-29T11:00:00+09:00"}}
    local = {"X": {"status": "error", "last_run": "(없음)"}}
    assert runlog.merge_by_recency(remote, local)["X"]["status"] == "completed"
