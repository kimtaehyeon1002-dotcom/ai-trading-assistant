"""자산 스냅샷 로컬 원장(design/20 Phase 8) — append·전일 조회·90일 히스토리."""
from __future__ import annotations

from repositories import asset_snapshot_repository as snap


def test_append_and_read_back(tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(snap, "_FILE", tmp_path / "history.json")
    snap.append_snapshot(100.0, {"kiwoom": 100.0})
    rows = snap.history()
    assert len(rows) == 1
    assert rows[0]["total_assets_krw"] == 100.0


def test_same_day_rerun_overwrites_not_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(snap, "_FILE", tmp_path / "history.json")
    snap.append_snapshot(100.0, {})
    snap.append_snapshot(150.0, {})  # 같은 날 재실행(하루 여러 빌드)
    rows = snap.history()
    assert len(rows) == 1
    assert rows[0]["total_assets_krw"] == 150.0


def test_previous_snapshot_excludes_today(tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(snap, "_FILE", tmp_path / "history.json")
    from utils.jsonio import save_json
    save_json(tmp_path / "history.json", [{"date": "2020-01-01", "total_assets_krw": 50.0, "accounts": {}}])
    snap.append_snapshot(100.0, {})  # 오늘 자
    prev = snap.previous_snapshot()
    assert prev["total_assets_krw"] == 50.0


def test_previous_snapshot_none_when_no_history(tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(snap, "_FILE", tmp_path / "history.json")
    assert snap.previous_snapshot() is None
