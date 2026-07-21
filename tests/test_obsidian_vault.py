from utils.frontmatter import parse as parse_frontmatter


def test_frontmatter_basic_types():
    text = (
        "---\n"
        '종목명: 삼성전자\n'
        '티커: "005930"\n'
        "목표가: 90000\n"
        "메모:\n"
        "---\n"
        "본문 영역\n"
    )
    fm, body = parse_frontmatter(text)
    assert fm == {"종목명": "삼성전자", "티커": "005930", "목표가": 90000, "메모": ""}
    assert body.strip() == "본문 영역"


def test_frontmatter_missing_block_returns_empty():
    fm, body = parse_frontmatter("그냥 본문만 있는 노트")
    assert fm == {}
    assert body == "그냥 본문만 있는 노트"


def test_obsidian_collector_scans_vault(tmp_path, monkeypatch):
    from collectors import obsidian_collector

    watchlist_dir = tmp_path / "00_Watchlist"
    watchlist_dir.mkdir()
    (watchlist_dir / "삼성전자.md").write_text(
        '---\n종목명: 삼성전자\n티커: "005930"\n시장: KRX\n---\n메모\n', encoding="utf-8"
    )
    (watchlist_dir / "빈노트.md").write_text("frontmatter 없음", encoding="utf-8")

    monkeypatch.setattr(obsidian_collector, "VAULT_WATCHLIST_DIR", watchlist_dir)
    monkeypatch.setattr(obsidian_collector, "_CACHE", tmp_path / "cache" / "vault_watchlist.json")

    assert obsidian_collector.enabled() is True
    raw = obsidian_collector.collect()
    assert raw == {"watchlist": [{"종목명": "삼성전자", "티커": "005930", "시장": "KRX"}]}


def test_obsidian_collector_disabled_when_empty(tmp_path, monkeypatch):
    from collectors import obsidian_collector

    empty_dir = tmp_path / "00_Watchlist"
    monkeypatch.setattr(obsidian_collector, "VAULT_WATCHLIST_DIR", empty_dir)
    assert obsidian_collector.enabled() is False
    assert obsidian_collector.collect() is None


def test_obsidian_repository_round_trip(tmp_path, monkeypatch):
    from repositories import obsidian_repository

    monkeypatch.setattr(obsidian_repository, "_CACHE", tmp_path / "vault_erp.json")
    raw = {"watchlist": [{"종목명": "삼성전자", "티커": "005930", "시장": "KRX"}]}

    obsidian_repository.save_normalized(raw)
    loaded = obsidian_repository.load_normalized()

    assert loaded["databases"] == raw
    assert "as_of" in loaded


def test_obsidian_repository_load_missing_returns_none(tmp_path, monkeypatch):
    from repositories import obsidian_repository

    monkeypatch.setattr(obsidian_repository, "_CACHE", tmp_path / "does_not_exist.json")
    assert obsidian_repository.load_normalized() is None


def test_erp_stats_only_watchlist_skips_assets_section():
    """assets/goals/cashflow가 비어도(워치리스트만 있어도) erp는 None이 아니어야 하고,
    자산 섹션은 대시보드 템플릿의 자체 {% if erp.assets_by_type %} 가드로 생략된다."""
    from calculators import erp_stats

    erp = erp_stats.summarize(
        {"as_of": "2026-07-21T00:00:00+09:00", "databases": {"watchlist": [{"종목명": "삼성전자"}]}}
    )
    assert erp is not None
    assert erp["assets_by_type"] == {}
    assert erp["total_assets"] == 0
    assert erp["watchlist"] == [{"종목명": "삼성전자"}]
