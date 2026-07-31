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


# ── 주말 정지 정책(design/26 §8-8) ────────────────────────────────────────────
# 크론과 SLO가 어긋나면 토·일 내내 가짜 위반이 쏟아진다. 아래 4개가 그 계약을 고정한다.


def _weekend_idle(now: datetime) -> dict:
    """새 주말 스케줄대로 각 워커가 **마지막으로 정상 실행됐을** 시각을 합성한다.

    시각은 실제 cron(UTC)에서 환산한다 — 대충 "금요일 밤"으로 잡으면 안 된다.
      macro      `0 * * * 1-5`   → 금 23:00 UTC = 토 08:00 KST
      stock      `0 22 * * 1-5`  → 금 22:00 UTC = 토 07:00 KST (미국 금요일 종가 수집)
      financials `0 21 * * 0-4`  → 목 21:00 UTC = 금 06:00 KST
      morning    `30 21 * * 0-4` → 목 21:30 UTC = 금 06:30 KST
      news       주말 2시간 주기 → 계속 돈다
    """
    macro_last = datetime(2026, 8, 1, 8, 0, tzinfo=TIMEZONE)     # 토 08:00 KST
    stock_last = datetime(2026, 8, 1, 7, 0, tzinfo=TIMEZONE)     # 토 07:00 KST
    daily_last = datetime(2026, 7, 31, 6, 0, tzinfo=TIMEZONE)    # 금 06:00 KST
    workers = {}
    for name, spec in slo.WORKERS.items():
        if spec.owner.startswith("macro"):
            last = macro_last
        elif spec.owner.startswith("stock"):
            last = stock_last
        elif spec.owner.startswith(("financials", "morning")) or spec.tier == slo.TIER_DESKTOP:
            last = daily_last
        else:  # news.yml 계열 — 주말에도 2시간마다 돈다
            last = now - timedelta(hours=2)
        workers[name] = {
            "worker": name, "status": spec.status_ok[0], "last_run": last.isoformat(),
            "items": spec.min_items if spec.min_items is not None else 1, "duration_ms": 5,
        }
    return workers


def test_weekend_idle_produces_no_violations():
    """주말 정지는 정상 운영이다 — 센서가 조용해야 한다."""
    sunday = datetime(2026, 8, 2, 12, 0, tzinfo=TIMEZONE)
    assert check_workers(_weekend_idle(sunday), sunday) == []


def test_monday_resume_boundary_produces_no_violations():
    """월 09:00 KST 재개 직전이 공백 최대 지점 — 여기서 안 터져야 임계값이 맞는 것이다."""
    monday = datetime(2026, 8, 3, 8, 55, tzinfo=TIMEZONE)
    assert check_workers(_weekend_idle(monday), monday) == []


def test_weekend_does_not_mask_a_real_failure():
    """정지 정책이 장애를 가리면 안 된다 — 상태 규칙은 주말에도 그대로 적용된다."""
    sunday = datetime(2026, 8, 2, 12, 0, tzinfo=TIMEZONE)
    workers = _weekend_idle(sunday)
    workers["News Research"] |= {"status": "error", "last_error": "RSS 전량 실패"}
    ids = [v["id"] for v in check_workers(workers, sunday)]
    assert "w.news-research.status" in ids


def test_weekend_threshold_still_has_an_upper_bound():
    """주말이라도 한계는 있다 — 2주 전 기록이면 잡혀야 한다."""
    sunday = datetime(2026, 8, 2, 12, 0, tzinfo=TIMEZONE)
    workers = _weekend_idle(sunday)
    workers["Macro FRED"] |= {"last_run": (sunday - timedelta(days=14)).isoformat()}
    ids = [v["id"] for v in check_workers(workers, sunday)]
    assert "w.macro-fred.stale" in ids
