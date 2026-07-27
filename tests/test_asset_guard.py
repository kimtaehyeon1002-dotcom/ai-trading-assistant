"""자산 평문 유출 가드(design/20 Phase 8 DoD 1·6) — pre-commit·CI 공용 로직 검증."""
from __future__ import annotations

from scripts.check_no_plaintext_assets import check_paths


def test_flags_sensitive_key_with_raw_number(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"balance": 84120000}', encoding="utf-8")
    violations = check_paths([str(bad)])
    assert len(violations) == 1
    assert "balance" in violations[0]


def test_flags_real_payload_field_names(tmp_path):
    """★회귀: 초기 가드는 어간 뒤 닫는 따옴표를 요구해 실제 필드(balance_krw 등)를 전부 놓쳤다.

    repositories/asset_repository.py가 실제로 쓰는 이름들이므로, 이 케이스가 깨지면
    "최후 방어선"이 실전에서 무효라는 뜻이다(design/20 Phase 8 DoD 1·6)."""
    real_fields = [
        '{"balance_krw": 84120000}',
        '{"total_assets_krw": 167504000}',
        '{"goal_amount_krw": 250000000}',
        '{"eval_pnl_krw": 9340000}',
        '{"value_krw": 10116000}',
        '{"usd_value": 12845.20}',
        '{"amount_krw": 116570000}',
    ]
    for i, content in enumerate(real_fields):
        bad = tmp_path / f"bad{i}.json"
        bad.write_text(content, encoding="utf-8")
        assert check_paths([str(bad)]), f"놓침: {content}"


def test_allows_relative_value_fields(tmp_path):
    """D안(상대값만 공개)이 성립하려면 %·비중 키는 통과해야 한다."""
    good = tmp_path / "public.json"
    good.write_text(
        '{"weight_pct": 15.7, "change_pct": -0.39, "goal_progress_pct": 67.0, "eval_pnl_pct": 12.49}',
        encoding="utf-8",
    )
    assert check_paths([str(good)]) == []


def test_allows_percentage_and_ciphertext_fields(tmp_path):
    good = tmp_path / "good.json"
    good.write_text('{"balance_pct": 50.2, "ciphertext": "aGVsbG8="}', encoding="utf-8")
    assert check_paths([str(good)]) == []


def test_flags_data_snapshots_path_regardless_of_content():
    violations = check_paths(["data/snapshots/2026-07-21.json"])
    assert len(violations) == 1
    assert "data/snapshots" in violations[0]


def test_allows_public_stock_fields_no_false_positive(tmp_path):
    """Phase 7 공개 데이터(거래대금 등)와 키 이름이 겹치지 않아야 한다(오탐 방지 회귀)."""
    rankings = tmp_path / "rankings.json"
    rankings.write_text('{"amount": 6614607186368, "close": 244000, "marcap": 1426491980352000}', encoding="utf-8")
    assert check_paths([str(rankings)]) == []


def test_ignores_missing_or_nonfile_paths():
    assert check_paths(["no/such/file.json", "some/dir/"]) == []


def test_tests_and_scripts_dirs_excluded_from_content_scan(tmp_path):
    """테스트 픽스처·가드 소스는 합성 금액을 의도적으로 포함하므로 내용 스캔에서 제외된다
    (pre-commit 훅이 전체 스테이징을 스캔할 때 자기 자신의 테스트를 영구 차단하지 않도록)."""
    assert check_paths(["ai_trading_assistant/tests/test_asset_crypto.py"]) == []
    assert check_paths(["scripts/check_no_plaintext_assets.py"]) == []
    # 단, tests/ 밑이라도 data/snapshots/ 경로는 여전히 차단된다(경로 규칙이 내용 제외보다 우선)
    assert check_paths(["tests/fixtures/data/snapshots/x.json"]) != []
