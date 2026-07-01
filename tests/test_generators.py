"""템플릿 렌더 스모크 — 샘플 데이터로 페이지가 실제로 생성되는지(jinja2 필요)."""
from config.settings import ensure_dirs
from generators.base import copy_static
from generators.dashboard.generate import generate as gen_dashboard
from generators.trades.generate import generate as gen_trades


def test_trades_page_renders():
    ensure_dirs()
    out = gen_trades()
    html = out.read_text(encoding="utf-8")
    assert out.exists() and html.strip()
    assert "매매일지" in html
    assert "삼성전자" in html  # 샘플 데이터 렌더 확인


def test_dashboard_renders_and_static_copies():
    ensure_dirs()
    out = gen_dashboard()
    copy_static()
    html = out.read_text(encoding="utf-8")
    assert "대시보드" in html
    assert (out.parent / "static" / "css" / "style.css").exists()
    assert (out.parent / ".nojekyll").exists()
