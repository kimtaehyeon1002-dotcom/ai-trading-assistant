"""매매일지 v2 렌더 스모크(design/20 Phase 8 "공개 v2 치환") — 합성 데이터로 결정적 검증.

이전에는 tests/test_generators.py가 v1 생성기를 간접적으로 스모크 테스트했으나, Phase 9에서
v1 셸(base.html)과 함께 그 생성기들이 소스에서 제거됐다 — trades_v2는 실제 render 대상이므로
동등한 커버리지를 여기서 새로 확보한다.
"""
from __future__ import annotations

from calculators.trade_stats import compute_stats
from config import nav
from generators.base import render
from models.trade import CATEGORY_LABELS, Trade


def _sample_context():
    trades = [
        Trade(date="2026-07-01", ticker="005930", name="삼성전자", buy_price=70000, sell_price=72000,
              quantity=10, holding_days=2, account_type="위탁", broker="kiwoom"),
    ]
    stats = compute_stats(trades)
    return {
        "root": "..",
        "nav": nav.context(active="trades"),
        "generated_at": "2026-07-01 09:00 KST",
        "trades": trades,
        "stats": stats,
        "labels": CATEGORY_LABELS,
    }


def test_rendered_trades_v2_is_v2_shell_with_expected_cards(tmp_path):
    out = render("pages/trades_v2.html", _sample_context(), tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert 'class="v2-sidebar"' in html
    for card_id in ("trades-summary", "trades-by-category", "trades-history"):
        assert f'id="{card_id}"' in html, f"{card_id} 카드 누락"
    assert "삼성전자" in html
    assert "static/js/trades.js" in html


def test_rendered_trades_v2_shows_empty_state_without_trades(tmp_path):
    ctx = _sample_context()
    ctx["trades"] = []
    ctx["stats"] = compute_stats([])
    out = render("pages/trades_v2.html", ctx, tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "기록된 매매가 없습니다" in html
