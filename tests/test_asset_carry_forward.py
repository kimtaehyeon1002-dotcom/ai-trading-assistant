"""자산 계좌 승계 검증(design/28) — 수집 주체가 둘로 갈린 뒤 서로 덮어쓰지 않는지.

CI(KIS·BYBIT)와 데스크톱(Kiwoom)이 같은 `assets.enc.json`에 쓴다. 각자 자기가 못 본 계좌를
결측으로 발행하면 상대가 넣은 값이 매번 사라져 총자산이 주체마다 널뛴다 — runlog.json
유실 사고와 같은 구조다. 아래 테스트가 그 계약을 고정한다.
"""
from __future__ import annotations

import pytest

from repositories import asset_repository as R


def _acct(role: str, balance: float | None, **kw) -> dict:
    return {"role": role, "label": role, "balance_krw": balance, "change_pct": 1.5, **kw}


PUBLISHED = {
    "kiwoom": {**_acct("kiwoom", 1_000_000), "_as_of": "2026-08-09T22:00:00+00:00"},
    "bybit": {**_acct("bybit", 500_000), "_as_of": "2026-08-09T22:00:00+00:00"},
}


# ── 승계 규칙 ────────────────────────────────────────────────────────────────


def test_missing_account_is_carried_from_published():
    """CI에는 Kiwoom OCX가 없다 — 결측으로 발행하면 화면에서 키움이 사라진다."""
    accounts = [_acct("kiwoom", None), _acct("bybit", 500_000)]
    merged, carried = R.carry_forward(accounts, PUBLISHED)
    assert carried == ["kiwoom"]
    assert merged[0]["balance_krw"] == 1_000_000


def test_collected_account_is_never_overwritten_by_published():
    """이번에 수집한 값이 항상 이긴다 — 승계는 빈자리를 메우는 것이지 덮는 게 아니다."""
    accounts = [_acct("bybit", 777_000)]
    merged, carried = R.carry_forward(accounts, PUBLISHED)
    assert carried == []
    assert merged[0]["balance_krw"] == 777_000


def test_carried_account_drops_day_change():
    """승계값의 전일 대비는 '어제 대비 어제'라 의미가 없다."""
    merged, _ = R.carry_forward([_acct("kiwoom", None)], PUBLISHED)
    assert merged[0]["change_pct"] is None


def test_carried_from_records_original_time():
    merged, _ = R.carry_forward([_acct("kiwoom", None)], PUBLISHED)
    assert merged[0]["carried_from"] == "2026-08-09T22:00:00+00:00"


def test_repeated_carry_does_not_reset_the_age():
    """승계를 거듭해도 값의 나이가 정직하게 늘어나야 한다 — carried_from을 새로 찍지 않는다."""
    once, _ = R.carry_forward([_acct("kiwoom", None)], PUBLISHED)
    republished = {"kiwoom": {**once[0], "_as_of": "2026-08-10T22:00:00+00:00"}}
    twice, _ = R.carry_forward([_acct("kiwoom", None)], republished)
    assert twice[0]["carried_from"] == "2026-08-09T22:00:00+00:00"


def test_nothing_to_carry_stays_missing():
    """직전 발행물에도 없으면 진짜 결측이다 — 가짜 값을 만들지 않는다."""
    merged, carried = R.carry_forward([_acct("kis_isa", None)], PUBLISHED)
    assert carried == []
    assert merged[0]["balance_krw"] is None


def test_internal_marker_is_not_published():
    """_as_of는 로딩용 내부 필드 — 발행 payload에 새어 나가면 안 된다."""
    merged, _ = R.carry_forward([_acct("kiwoom", None)], PUBLISHED)
    assert "_as_of" not in merged[0]


# ── payload 반영 ─────────────────────────────────────────────────────────────


def test_payload_reports_carried_roles():
    merged, carried = R.carry_forward([_acct("kiwoom", None), _acct("bybit", 500_000)], PUBLISHED)
    payload = R.build_payload(merged, carried=carried)
    assert payload["carried_roles"] == ["kiwoom"]


def test_carried_blocks_day_change_like_missing_does(monkeypatch):
    """승계분이 섞인 합계로 전일 대비를 내면 일부가 '어제 대비 어제'가 된다."""
    monkeypatch.setattr(R.asset_snapshot_repository, "previous_snapshot",
                        lambda: {"date": "2026-08-09", "total_assets_krw": 1_400_000})
    monkeypatch.setattr(R.asset_snapshot_repository, "history", lambda n: [])
    merged, carried = R.carry_forward([_acct("kiwoom", None), _acct("bybit", 500_000)], PUBLISHED)
    assert R.build_payload(merged, carried=carried)["day_change_pct"] is None


def test_day_change_survives_when_everything_is_fresh(monkeypatch):
    monkeypatch.setattr(R.asset_snapshot_repository, "previous_snapshot",
                        lambda: {"date": "2026-08-09", "total_assets_krw": 1_000_000})
    monkeypatch.setattr(R.asset_snapshot_repository, "history", lambda n: [])
    payload = R.build_payload([_acct("kiwoom", 1_100_000)], carried=[])
    assert payload["day_change_pct"] == 10.0


# ── 발행물 로딩 ──────────────────────────────────────────────────────────────


def test_load_published_returns_empty_without_passphrase(monkeypatch):
    monkeypatch.setattr(R, "ASSET_PASSPHRASE", "")
    assert R.load_published_accounts() == {}


def test_load_published_roundtrip(tmp_path, monkeypatch):
    from utils.crypto import encrypt
    from utils.jsonio import save_json

    path = tmp_path / "assets.enc.json"
    monkeypatch.setattr(R, "ASSET_PASSPHRASE", "pw")
    monkeypatch.setattr(R, "_PUBLISHED", path)
    save_json(path, encrypt({"as_of": "2026-08-09T22:00:00+00:00",
                             "accounts": [_acct("kiwoom", 1_000_000)]}, "pw"))

    loaded = R.load_published_accounts()
    assert loaded["kiwoom"]["balance_krw"] == 1_000_000
    assert loaded["kiwoom"]["_as_of"] == "2026-08-09T22:00:00+00:00"


def test_wrong_passphrase_does_not_block_publishing(tmp_path, monkeypatch):
    """열쇠가 어긋나도 발행은 계속돼야 한다 — 승계만 포기한다."""
    from utils.crypto import encrypt
    from utils.jsonio import save_json

    path = tmp_path / "assets.enc.json"
    save_json(path, encrypt({"as_of": "x", "accounts": [_acct("kiwoom", 1)]}, "right"))
    monkeypatch.setattr(R, "ASSET_PASSPHRASE", "wrong")
    monkeypatch.setattr(R, "_PUBLISHED", path)
    assert R.load_published_accounts() == {}


def test_missing_published_file_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "ASSET_PASSPHRASE", "pw")
    monkeypatch.setattr(R, "_PUBLISHED", tmp_path / "none.json")
    assert R.load_published_accounts() == {}


@pytest.mark.parametrize("role", ["kiwoom", "kis_isa", "kis_foreign", "bybit"])
def test_every_role_can_be_carried(role):
    published = {role: {**_acct(role, 123_456), "_as_of": "2026-08-09T22:00:00+00:00"}}
    merged, carried = R.carry_forward([_acct(role, None)], published)
    assert carried == [role] and merged[0]["balance_krw"] == 123_456
