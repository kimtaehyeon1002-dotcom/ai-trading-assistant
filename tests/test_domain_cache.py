"""design/25 Phase A — 도메인 캐시 계약(항목별 last-good 폴백 + 나이 상한)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from utils import domain_cache


def _item(hours_ago: float, value: float = 1.0) -> dict:
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"envelope": {"value": value, "as_of_iso": stamp}}


def test_missing_key_is_filled_from_previous():
    new = {"CPI": None, "GDP": _item(0)}
    merged, carried = domain_cache.merge_last_good(new, {"CPI": _item(5)})
    assert carried == ["CPI"]
    assert merged["CPI"]["envelope"]["value"] == 1.0


def test_carried_item_keeps_its_original_as_of():
    """폴백 값이 새 값인 척하면 안 된다 — 원래 시각을 그대로 달고 나가야 배지가 정직해진다."""
    old = _item(30)
    merged, _ = domain_cache.merge_last_good({"CPI": None}, {"CPI": old})
    assert merged["CPI"]["envelope"]["as_of_iso"] == old["envelope"]["as_of_iso"]


def test_new_value_always_wins():
    merged, carried = domain_cache.merge_last_good({"CPI": _item(0, 99.0)}, {"CPI": _item(1, 1.0)})
    assert merged["CPI"]["envelope"]["value"] == 99.0 and carried == []


def test_item_older_than_cap_is_dropped():
    """낡은 값보다 빈칸이 낫다."""
    merged, carried = domain_cache.merge_last_good(
        {"CPI": None}, {"CPI": _item(200)}, max_age_h=24)
    assert merged["CPI"] is None and carried == []


def test_item_without_timestamp_is_not_carried():
    """나이를 알 수 없는 값은 폴백하지 않는다 — 얼마나 낡았는지 말할 수 없으면 쓰지 않는다."""
    merged, carried = domain_cache.merge_last_good({"CPI": None}, {"CPI": {"envelope": {"value": 1}}})
    assert merged["CPI"] is None and carried == []


def test_save_skips_when_everything_is_missing(tmp_path):
    """전량 결측이 직전 발행물을 덮으면 안 된다 — CI 일시 장애로 페이지가 비는 것을 막는다."""
    path = tmp_path / "indicators.json"
    good = {"CPI": _item(1), "GDP": _item(1)}
    path.write_text(json.dumps(good), encoding="utf-8")
    result = domain_cache.save_keyed(path, {"CPI": None, "GDP": None}, max_age_h=0.001)
    assert result == good
    assert json.loads(path.read_text(encoding="utf-8")) == good  # 파일이 그대로다


def test_save_writes_merged_result(tmp_path):
    path = tmp_path / "indicators.json"
    path.write_text(json.dumps({"CPI": _item(2)}), encoding="utf-8")
    result = domain_cache.save_keyed(path, {"CPI": None, "GDP": _item(0)})
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == result
    assert on_disk["CPI"] is not None and on_disk["GDP"] is not None


def test_first_run_without_previous_file_just_saves(tmp_path):
    path = tmp_path / "indicators.json"
    result = domain_cache.save_keyed(path, {"CPI": _item(0)})
    assert path.exists() and result["CPI"] is not None


def test_corrupt_previous_file_is_tolerated(tmp_path):
    path = tmp_path / "indicators.json"
    path.write_text("not json", encoding="utf-8")
    assert domain_cache.load_previous(path) == {}
