"""원격 runlog 병합 검증 — 데스크톱 배포와 CI commit-push 액션이 공유하는 단일 구현.

이 병합이 틀리면 두 방향의 사고가 난다:
  · 병합을 안 하면 → 상대가 기록한 워커가 사라진다(2026-07-28 실제 사고)
  · 낡은 쪽을 채택하면 → 루프 센서가 가짜 stale 위반을 낸다
둘 다 조용히 일어나므로 테스트로 고정한다.
"""
from __future__ import annotations

import json

import pytest

from scripts import merge_remote_runlog as M
from utils.jsonio import load_json, save_json


def _runlog(workers: dict) -> dict:
    return {"updated_at": "2026-07-30T10:00:00+09:00", "workers": workers}


def _w(name: str, last_run: str, status: str = "completed") -> dict:
    return {"worker": name, "status": status, "last_run": last_run}


@pytest.fixture
def local(tmp_path):
    path = tmp_path / "runlog.json"
    save_json(path, _runlog({"News Research": _w("News Research", "2026-07-30T10:05:00+09:00")}))
    return path


def _patch_remote(monkeypatch, payload):
    monkeypatch.setattr(M, "_show", lambda ref, rel, cwd: payload)


def test_remote_only_worker_is_restored(monkeypatch, local):
    """CI만 기록하는 워커(FS DART 등)가 데스크톱 사본에 덮여 사라지던 사고의 회귀 테스트."""
    _patch_remote(monkeypatch, _runlog({"FS DART corpCode": _w("FS DART corpCode", "2026-07-30T06:00:00+09:00")}))
    assert M.merge_from_ref(path=local) == 1
    workers = load_json(local)["workers"]
    assert set(workers) == {"News Research", "FS DART corpCode"}


def test_newer_remote_record_wins(monkeypatch, local):
    """로컬 사본의 낡은 기록이 원격 최신을 덮으면 가짜 stale이 생긴다."""
    _patch_remote(monkeypatch, _runlog({"News Research": _w("News Research", "2026-07-30T11:00:00+09:00")}))
    M.merge_from_ref(path=local)
    assert load_json(local)["workers"]["News Research"]["last_run"].startswith("2026-07-30T11:00")


def test_newer_local_record_wins(monkeypatch, local):
    _patch_remote(monkeypatch, _runlog({"News Research": _w("News Research", "2026-07-29T09:00:00+09:00")}))
    M.merge_from_ref(path=local)
    assert load_json(local)["workers"]["News Research"]["last_run"].startswith("2026-07-30T10:05")


def test_identical_content_is_a_noop(monkeypatch, local):
    """변화가 없으면 파일을 건드리지 않는다 — 빈 커밋·불필요한 amend 방지."""
    _patch_remote(monkeypatch, load_json(local))
    assert M.merge_from_ref(path=local) == 0


def test_unreadable_ref_does_not_block_deploy(monkeypatch, local):
    """첫 배포·shallow clone 등 ref를 못 읽는 경우가 있다 — 배포를 막을 자격이 없다."""
    _patch_remote(monkeypatch, None)
    before = local.read_text(encoding="utf-8")
    assert M.merge_from_ref(path=local) == 0
    assert local.read_text(encoding="utf-8") == before


def test_missing_local_file_is_tolerated(monkeypatch, tmp_path):
    _patch_remote(monkeypatch, _runlog({"X": _w("X", "2026-07-30T10:00:00+09:00")}))
    assert M.merge_from_ref(path=tmp_path / "none.json") == 0


def test_other_top_level_keys_are_preserved(monkeypatch, local):
    """updated_at 등 workers 밖의 필드를 잃지 않는다."""
    _patch_remote(monkeypatch, _runlog({"FS DART corpCode": _w("FS DART corpCode", "2026-07-30T06:00:00+09:00")}))
    M.merge_from_ref(path=local)
    assert load_json(local)["updated_at"] == "2026-07-30T10:00:00+09:00"


def test_show_returns_none_for_bad_ref(tmp_path):
    """_show는 예외가 아니라 None으로 실패를 알린다(호출부가 배포를 계속할 수 있게)."""
    assert M._show("no-such-ref-xyz", "docs/ai-office/runlog.json", tmp_path) is None


def test_malformed_remote_json_is_ignored(monkeypatch, local):
    monkeypatch.setattr(M, "_show", lambda ref, rel, cwd: None)  # _show가 파싱 실패를 None으로 흡수
    before = json.loads(local.read_text(encoding="utf-8"))
    M.merge_from_ref(path=local)
    assert json.loads(local.read_text(encoding="utf-8")) == before
