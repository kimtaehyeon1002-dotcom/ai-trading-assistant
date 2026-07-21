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

    stub = tmp_path / "20_Memory" / "themes" / "AI.md"
    assert stub.exists()
    assert "테마: AI" in stub.read_text(encoding="utf-8")


def test_write_morning_skipped_when_vault_missing(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path / "no_such_dir")
    assert vault_journal.enabled() is False
    assert vault_journal.write_morning() is None


def test_write_news_groups_by_category(tmp_path, monkeypatch):
    from generators import vault_journal

    _patch_vault_dirs(monkeypatch, vault_journal, tmp_path)
    a1 = NewsArticle(title="속보 기사", link="https://example.com/1", source="A", categories=["breaking"])
    a2 = NewsArticle(title="반도체 기사", link="https://example.com/2", source="B", categories=["semiconductor"])
    monkeypatch.setattr(vault_journal.pipelines, "get_news", lambda: [a1, a2])

    out = vault_journal.write_news()
    text = out.read_text(encoding="utf-8")
    assert "## 속보" in text and "속보 기사" in text
    assert "## 반도체" in text and "반도체 기사" in text


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

    stub_path = tmp_path / "20_Memory" / "stocks" / "삼성전자.md"
    assert stub_path.exists()
    stub_path.write_text("사용자가 이미 작성한 메모", encoding="utf-8")

    vault_journal.write_trades()  # 재실행해도 기존 스텁은 보존
    assert stub_path.read_text(encoding="utf-8") == "사용자가 이미 작성한 메모"
