"""루프 원장 + vault 투영 검증(design/26 §3-3·§3-8).

원장은 루프의 적분항이라 **기록이 조용히 변질되면 안 된다**. 여기 테스트의 절반은
"덮어쓰지 않음"을 지키는 회귀 테스트다.
"""
from __future__ import annotations

import pytest

from config.audit_rubric import REPORT_FIELDS
from utils import ledger


@pytest.fixture
def path(tmp_path):
    return tmp_path / "ledger.jsonl"


def _open(path, **kw):
    base = dict(id="a.x.y", state=ledger.STATE_OPEN, title="T", severity="major",
                source=ledger.SOURCE_AUDITOR, area="collectors", priority="P11", tier="cloud",
                문제점="P", 원인="C", 해결방법="S", 성능향상="G", 부작용="없음")
    return ledger.record(path=path, **{**base, **kw})


# ── 기본 왕복 ────────────────────────────────────────────────────────────────


def test_record_then_state_roundtrip(path):
    _open(path)
    issue = ledger.state(path)["a.x.y"]
    assert issue.state == ledger.STATE_OPEN
    assert issue.severity == "major"
    assert issue.report["해결방법"] == "S"
    assert issue.is_active


def test_all_report_fields_are_preserved(path):
    _open(path)
    assert set(ledger.state(path)["a.x.y"].report) == set(REPORT_FIELDS)


def test_unknown_report_field_raises(path):
    """오타 난 필드를 조용히 버리면 vault에서 영영 안 보인다."""
    with pytest.raises(ValueError, match="알 수 없는 리포트 필드"):
        ledger.record(path=path, id="a.x.y", state=ledger.STATE_OPEN, 해결방안="오타")


def test_unknown_state_raises(path):
    with pytest.raises(ValueError, match="알 수 없는 state"):
        ledger.record(path=path, id="a.x.y", state="done")


# ── 부분 갱신이 최초 기록을 덮지 않는다(실제 발생한 버그의 회귀) ──────────────


def test_state_transition_does_not_clobber_severity(path):
    """closed 전이 이벤트가 기본값 severity를 실어 critical을 major로 바꾼 적이 있다."""
    _open(path, severity="critical")
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_CLOSED, pr="#41")
    issue = ledger.state(path)["a.x.y"]
    assert issue.severity == "critical"
    assert issue.state == ledger.STATE_CLOSED
    assert issue.pr == "#41"


def test_transition_keeps_report_body(path):
    """전이 이벤트는 본문을 다시 싣지 않는다 — 그래도 본문이 남아야 한다."""
    _open(path)
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_CLOSED)
    assert ledger.state(path)["a.x.y"].report["문제점"] == "P"


def test_source_is_first_wins(path):
    """source는 '최초 발견자' — 주체별 오탐률 집계축이라 전이 행위자가 덮으면 안 된다."""
    _open(path, source=ledger.SOURCE_PROBE)
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_FIXING,
                  source=ledger.SOURCE_AUDITOR, attempt=1)
    assert ledger.state(path)["a.x.y"].source == ledger.SOURCE_PROBE


def test_first_seen_is_earliest_and_last_seen_moves(path):
    _open(path)
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_CLOSED)
    issue = ledger.state(path)["a.x.y"]
    assert issue.first_seen <= issue.last_seen


# ── 대상 선택(WIP=1) ─────────────────────────────────────────────────────────


def test_next_target_skips_desktop_tier(path):
    """클라우드가 검증할 수 없는 것을 고치게 두면 상상으로 고친다(design/26 A-2)."""
    _open(path, id="d.asset.kiwoom", severity="critical", tier="desktop")
    _open(path, id="c.collectors.http", severity="major", tier="cloud")
    assert ledger.next_target(path).id == "c.collectors.http"


def test_next_target_skips_exhausted_attempts(path):
    _open(path, id="a.stuck")
    ledger.record(path=path, id="a.stuck", state=ledger.STATE_OPEN, attempt=ledger.MAX_ATTEMPTS)
    _open(path, id="a.fresh", severity="minor")
    assert ledger.next_target(path).id == "a.fresh"


def test_next_target_none_when_nothing_actionable(path):
    _open(path)
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_CLOSED)
    assert ledger.next_target(path) is None


def test_active_sorted_by_severity_then_age(path):
    _open(path, id="a.minor", severity="minor")
    _open(path, id="a.critical", severity="critical")
    _open(path, id="a.major", severity="major")
    assert [i.id for i in ledger.active(path)] == ["a.critical", "a.major", "a.minor"]


def test_terminal_states_are_not_active(path):
    for i, state in enumerate(ledger.TERMINAL_STATES):
        _open(path, id=f"a.t{i}")
        ledger.record(path=path, id=f"a.t{i}", state=state)
    assert ledger.active(path) == []


def test_should_escalate_at_attempt_limit(path):
    _open(path)
    ledger.record(path=path, id="a.x.y", state=ledger.STATE_OPEN, attempt=ledger.MAX_ATTEMPTS)
    assert ledger.should_escalate(ledger.state(path)["a.x.y"])


# ── 내구성 ───────────────────────────────────────────────────────────────────


def test_broken_line_does_not_kill_the_ledger(path):
    _open(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write("{깨진 줄\n\n")
    _open(path, id="a.after")
    assert set(ledger.state(path)) == {"a.x.y", "a.after"}


def test_missing_file_is_empty_not_error(tmp_path):
    assert ledger.state(tmp_path / "none.jsonl") == {}


# ── vault 투영 ───────────────────────────────────────────────────────────────


def _patch_vault(monkeypatch, vault_ops, tmp_path, ledger_path):
    monkeypatch.setattr(vault_ops, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(vault_ops, "_OPS", tmp_path / "50_Ops" / "loop")
    monkeypatch.setattr(vault_ops, "_INDEX", tmp_path / "50_Ops" / "loop" / "INDEX.md")
    monkeypatch.setattr(vault_ops.ledger, "LEDGER_PATH", ledger_path)


def test_vault_note_carries_query_axes_and_all_sections(tmp_path, monkeypatch, path):
    from generators import vault_ops

    _open(path, severity="critical")
    _patch_vault(monkeypatch, vault_ops, tmp_path, path)
    written = vault_ops.write_issues()

    note = (tmp_path / "50_Ops" / "loop" / "a.x.y.md").read_text(encoding="utf-8")
    assert "type: loop-issue" in note          # 스키마 계약: Dataview 조회축
    assert "state: open" in note
    assert "severity: critical" in note
    assert "priority: P11" in note and "우선순위:" in note
    for field in REPORT_FIELDS:
        assert f"## {field}" in note
    assert any(p.name == "INDEX.md" for p in written)


def test_vault_write_is_idempotent(tmp_path, monkeypatch, path):
    """내용이 같으면 쓰지 않는다 — mtime만 바뀌어도 vault git이 빈 커밋을 만든다."""
    from generators import vault_ops

    _open(path)
    _patch_vault(monkeypatch, vault_ops, tmp_path, path)
    vault_ops.write_issues()
    assert vault_ops.write_issues() == []


def test_vault_skipped_when_missing(tmp_path, monkeypatch, path):
    from generators import vault_ops

    _open(path)
    _patch_vault(monkeypatch, vault_ops, tmp_path / "no_such_vault", path)
    assert vault_ops.write_issues() == []


def test_index_lists_escalated_separately(tmp_path, monkeypatch, path):
    """사람이 봐야 하는 것(escalated)이 미해결 더미에 섞이면 안 된다."""
    from generators import vault_ops

    _open(path)
    _patch_vault(monkeypatch, vault_ops, tmp_path, path)
    vault_ops.write_issues()
    index = (tmp_path / "50_Ops" / "loop" / "INDEX.md").read_text(encoding="utf-8")
    assert 'state = "escalated"' in index
    assert "loop-index" in index
