from models.market import Quote
from models.news import NewsArticle
from models.trade import Trade


def _patch_vault_dirs(monkeypatch, vault_journal, tmp_path):
    monkeypatch.setattr(vault_journal, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(vault_journal, "_JOURNAL", tmp_path / "10_Journal")
    monkeypatch.setattr(vault_journal, "_MEMORY_STOCKS", tmp_path / "20_Memory" / "stocks")
    monkeypatch.setattr(vault_journal, "_MEMORY_THEMES", tmp_path / "20_Memory" / "themes")


def test_write_morning_renders_market_news_and_theme_stub(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path)
    monkeypatch.setattr(
        vault_journal.pipelines,
        "get_market",
        lambda: {"nasdaq": Quote(symbol="^IXIC", name="나스닥", price=20000.0, change_pct=1.23)},
    )
    article = NewsArticle(title="AI 랠리", link="https://example.com/a", source="연합뉴스", categories=["ai"])
    monkeypatch.setattr(vault_journal.pipelines, "get_news", lambda: [article])
    monkeypatch.setattr(vault_journal.themes_calc, "extract_themes", lambda news, top_n=3: [{"name": "AI", "count": 1}])

    out = vault_journal.write_morning()
    assert out is not None and out.exists()
    text = out.read_text(encoding="utf-8")
    assert "나스닥" in text and "AI 랠리" in text and "[[20_Memory/themes/AI|AI]]" in text
    assert "themes: [AI]" in text  # 스키마 계약: 테마 조회축 frontmatter

    stub = (tmp_path / "20_Memory" / "themes" / "AI.md").read_text(encoding="utf-8")
    assert "테마: AI" in stub
    assert "테마로 뜬 날 (자동)" in stub and "contains(themes, this.테마)" in stub  # Dataview 내장


def test_write_morning_skipped_when_vault_missing(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path / "no_such_dir")
    assert vault_journal.enabled() is False
    assert vault_journal.write_morning() is None


def test_write_news_selects_top3_with_headlines_frontmatter(tmp_path, monkeypatch):
    """뉴스 저널 = 최중요 TOP3만 + DB 조회용 headlines frontmatter (전체 보존은 웹 아카이브 몫)."""
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path)
    articles = [
        NewsArticle(title="속보: 금리 \"동결\"", link="https://example.com/1", source="A", categories=["breaking"]),
        NewsArticle(title="반도체 기사", link="https://example.com/2", source="B", categories=["semiconductor"]),
        NewsArticle(title="매크로 기사", link="https://example.com/3", source="C", categories=["macro"]),
        NewsArticle(title="일반 기사", link="https://example.com/4", source="D", categories=["kr_market"]),
    ]
    monkeypatch.setattr(vault_journal.pipelines, "get_news", lambda: articles)

    out = vault_journal.write_news()
    text = out.read_text(encoding="utf-8")
    assert "뉴스 TOP 3" in text
    # 가중치(속보+3 > 반도체+1 = 매크로+1 > 일반)순 3건만 — 일반 기사는 탈락
    assert text.count("](https://example.com/") == 3
    assert "일반 기사" not in text
    assert "headlines:" in text
    assert '  - "속보: 금리 \\"동결\\""' in text  # YAML 이스케이프
    assert "· 속보" in text  # 카테고리 라벨 병기


def test_write_news_empty_is_honest(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path)
    monkeypatch.setattr(vault_journal.pipelines, "get_news", lambda: [])
    text = vault_journal.write_news().read_text(encoding="utf-8")
    assert "(수집된 뉴스 없음)" in text and "headlines:" not in text


def test_write_trades_groups_by_date_and_stubs_stock(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path)
    trades = [
        Trade(date="2026-07-01", ticker="005930", name="삼성전자", buy_price=100.0, sell_price=110.0,
              quantity=1.0, holding_days=0, broker="kiwoom"),
        Trade(date="2026-07-01", ticker="000660", name="SK하이닉스", buy_price=200.0, sell_price=180.0,
              quantity=1.0, holding_days=0, broker="kiwoom"),
        Trade(date="2026-07-02", ticker="005930", name="삼성전자", buy_price=90.0, sell_price=95.0,
              quantity=1.0, holding_days=0, broker="kiwoom"),
    ]
    monkeypatch.setattr(vault_journal.trade_repository, "load_trades", lambda: trades)

    written = vault_journal.write_trades()
    assert len(written) == 2  # 2026-07-01, 2026-07-02

    day1 = (tmp_path / "10_Journal" / "trades" / "2026-07-01.md").read_text(encoding="utf-8")
    assert "삼성전자" in day1 and "SK하이닉스" in day1
    assert "pnl: -10.0" in day1  # (110-100)*1 + (180-200)*1 = 10 - 20
    assert 'tickers: ["005930", "000660"]' in day1  # 스키마 계약: 종목 조회축(중복 제거)

    stub_path = tmp_path / "20_Memory" / "stocks" / "삼성전자.md"
    stub = stub_path.read_text(encoding="utf-8")
    assert "status: 관심" in stub
    assert "매매 기록 (자동)" in stub and "contains(tickers, this.티커)" in stub  # Dataview 내장
    stub_path.write_text("사용자가 이미 작성한 메모", encoding="utf-8")

    vault_journal.write_trades()  # 재실행해도 기존 스텁은 보존
    assert stub_path.read_text(encoding="utf-8") == "사용자가 이미 작성한 메모"
