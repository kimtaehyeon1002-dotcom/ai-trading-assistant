"""Phase 4 Dashboard(/) 치환 — 자산 평문 선차단·Hero 결측 생략·헤더 회귀(design/20 Phase 4).

카드 구조·자산 평문 검사는 실제 네트워크(yfinance/RSS)를 타는 generate()가 아니라 합성
컨텍스트로 템플릿을 직접 렌더링해 검증한다(다른 테스트와 동일하게 빠르고 결정적으로 유지 —
실데이터 파이프라인 자체의 정확성은 test_market_phase3.py 등에서 이미 별도로 검증됨).
"""
from __future__ import annotations

import re

from config.nav import context as nav_context
from generators.base import render
from generators.dashboard_v2.generate import _headline, _schedule_rows
from models.market import Quote
from models.news import NewsArticle

_ASSET_LEAK_RE = re.compile(r"[0-9]{3}[,0-9]*원|총자산|목표금액")


def _sample_context():
    q = Quote(symbol="sp500", name="S&P500", price=7492.0, change_pct=0.46)
    news = NewsArticle(title="샘플 기사", link="https://example.com/1", categories=["breaking"])
    return {
        "root": ".",
        "nav": nav_context(active="dashboard"),
        "generated_at": "2026-07-21 09:00 KST",
        "headline": "미국 3대 지수 상승 마감 · 코스피 ▲ 0.50%",
        "market": {"sp500": q, "nasdaq": q, "dow": q, "kospi": q, "kosdaq": q, "kospi_night": None, "usdkrw": q, "vix": q},
        "kr_tiles": [("kospi", q), ("kosdaq", q), ("kospi_night", None), ("usdkrw", q)],
        "us_tiles": [("sp500", q), ("nasdaq", q), ("dow", q), ("vix", q)],
        "top_news": [news],
        "recent_news": [(news, "속보")],
        "schedule": _schedule_rows(),
        "latest_morning": "2026-07-21",
    }


def _q(price, change_pct):
    return Quote(symbol="x", name="x", price=price, change_pct=change_pct)


# ---------- Hero 헤드라인 조립(사실 기반, 해석 없음) ----------

def test_headline_all_us_up_and_kospi_direction():
    market = {"sp500": _q(100, 1.0), "nasdaq": _q(100, 0.5), "dow": _q(100, 0.2), "kospi": _q(2600, -0.8)}
    h = _headline(market)
    assert h == "미국 3대 지수 상승 마감 · 코스피 ▼ 0.80%"


def test_headline_mixed_us_direction():
    market = {"sp500": _q(100, 1.0), "nasdaq": _q(100, -0.5), "dow": _q(100, 0.2)}
    assert _headline(market) == "미국 3대 지수 혼조 마감"


def test_headline_all_us_down():
    market = {"sp500": _q(100, -1.0), "nasdaq": _q(100, -0.5), "dow": _q(100, -0.2)}
    assert _headline(market) == "미국 3대 지수 하락 마감"


def test_headline_omitted_when_no_data():
    """DoD 3 — 데이터 결측 시 문장 행 자체를 생략한다(빈 문장 렌더 금지)."""
    assert _headline({}) is None
    assert _headline({"sp500": None, "nasdaq": None, "dow": None, "kospi": None}) is None


def test_headline_kospi_only_no_us_data():
    market = {"kospi": _q(2600, 0.5)}
    assert _headline(market) == "코스피 ▲ 0.50%"


# ---------- 오늘 일정(세션 룰 기반, 정렬) ----------

def test_schedule_rows_sorted_by_time_and_covers_kr_sessions():
    rows = _schedule_rows()
    times = [r["time"] for r in rows]
    assert times == sorted(times)
    labels = {r["label"] for r in rows}
    assert "국내 증시 개장" in labels
    assert "국내 증시 마감" in labels
    assert "야간선물 세션 개시" in labels
    assert "야간선물 세션 마감" in labels


# ---------- 자산 평문 선차단(DoD 2) — 템플릿 렌더 산출물 검사 ----------

def test_rendered_dashboard_has_zero_asset_leak_patterns(tmp_path):
    out = render("pages/dashboard_v2.html", _sample_context(), tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    matches = _ASSET_LEAK_RE.findall(html)
    assert matches == [], f"자산 평문/역산 가능 패턴 발견: {matches}"


def test_rendered_dashboard_is_v2_shell_with_exactly_five_cards(tmp_path):
    out = render("pages/dashboard_v2.html", _sample_context(), tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert 'class="v2-sidebar"' in html
    assert 'aria-current="page"' in html
    for card_id in ("dash-hero", "dash-kr", "dash-us", "dash-news", "dash-schedule"):
        assert f'id="{card_id}"' in html, f"{card_id} 카드 누락"
    # design/01 §3-1 "정확히 5개" 계약 — opt-in 카드(관심종목 등)는 없어야 한다
    assert html.count('class="v2-card ') == 5


def test_rendered_dashboard_updown_script_loaded(tmp_path):
    out = render("pages/dashboard_v2.html", _sample_context(), tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "static/js/updown.js" in html


def test_rendered_dashboard_omits_headline_row_when_none(tmp_path):
    ctx = _sample_context()
    ctx["headline"] = None
    out = render("pages/dashboard_v2.html", ctx, tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "v2-hero-headline" not in html


# ---------- news_categories.primary_label 우선순위 ----------

def test_primary_label_priority_breaking_over_macro():
    a = NewsArticle(title="t", link="l", categories=["kr_market", "macro", "breaking"])
    from calculators.news_categories import primary_label
    assert primary_label(a) == "속보"


def test_primary_label_macro_over_market():
    a = NewsArticle(title="t", link="l", categories=["kr_market", "macro"])
    from calculators.news_categories import primary_label
    assert primary_label(a) == "거시경제"


def test_primary_label_fallback_when_no_known_category():
    a = NewsArticle(title="t", link="l", categories=["ai"])
    from calculators.news_categories import primary_label
    assert primary_label(a) == "기타"
