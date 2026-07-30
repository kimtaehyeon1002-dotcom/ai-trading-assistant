"""design/25 §6-2 — Macro "금융시장" 스트립과 코인 한 줄 요약.

핵심 계약 3가지를 고정한다: ① 결측 키는 타일을 만들지 않는다(빈칸 렌더 금지) ② 이력이 없어도
스팟 타일은 살아남는다(미니차트만 생략) ③ 코인은 카드가 아니라 한 줄이다.
"""
from __future__ import annotations

from models.market import Quote
from repositories import macro_repository
from utils import sparkline as spark


def _q(name: str, price: float, change_pct: float | None = 1.0) -> Quote:
    return Quote(symbol="x", name=name, price=price, change_pct=change_pct)


# ---------- 스트립 ----------

def test_missing_keys_produce_no_tiles():
    """확보되지 않은 심볼은 타일 자체가 없어야 한다 — 빈 값 타일을 만들면 안 된다."""
    groups = macro_repository.build_market_strip({"usdkrw": _q("USD/KRW", 1400.0)}, {})
    keys = [t["key"] for g in groups for t in g["tiles"]]
    assert keys == ["usdkrw"]


def test_group_is_omitted_entirely_when_all_members_missing():
    groups = macro_repository.build_market_strip({"usdkrw": _q("USD/KRW", 1400.0)}, {})
    assert [g["name"] for g in groups] == ["환율·달러"]  # 금리·원자재 그룹은 통째로 생략


def test_tile_survives_missing_history_with_empty_spark():
    """이력 수집 실패는 미니차트만 잃는다 — 값·등락은 그대로다."""
    groups = macro_repository.build_market_strip({"vix": _q("VIX", 18.0, -2.0)}, {})
    tile = groups[0]["tiles"][0]
    assert tile["spark"] == ""
    assert tile["price"] == 18.0 and tile["change_pct"] == -2.0


def test_tile_with_history_renders_sparkline():
    groups = macro_repository.build_market_strip(
        {"gold": _q("금", 4000.0)}, {"gold": [3900.0, 3950.0, 4000.0]}
    )
    assert "<polyline" in groups[0]["tiles"][0]["spark"]


# ---------- 코인 한 줄 ----------

def _btc_krw(value: float = 92_000_000.0, premium: float | None = -0.28) -> dict:
    return {
        "envelope": {"value": value, "change_pct": -1.1, "as_of_iso": "2026-07-29T00:00:00+00:00"},
        "kimchi_premium_pct": premium,
    }


def test_crypto_line_combines_krw_usd_and_premium():
    line = macro_repository.build_crypto_line({"btc": _q("비트코인", 63_000.0)}, _btc_krw())
    assert line["krw"] == 92_000_000.0 and line["usd"] == 63_000.0
    assert line["kimchi_premium_pct"] == -0.28


def test_crypto_line_is_none_when_no_source_available():
    assert macro_repository.build_crypto_line({}, None) is None


def test_crypto_line_survives_upbit_only():
    line = macro_repository.build_crypto_line({}, _btc_krw())
    assert line["krw"] == 92_000_000.0 and "usd" not in line


# ---------- 스파크라인 헬퍼 ----------

def test_sparkline_needs_two_points_and_uses_no_hex():
    assert spark.sparkline_svg([100.0]) == ""
    svg = spark.sparkline_svg([100.0, 101.0, 99.0])
    assert "#" not in svg and "var(--market-" in svg


def test_sparkline_colors_by_direction_when_requested():
    up = spark.sparkline_svg([100.0, 105.0], color_by_direction=True)
    down = spark.sparkline_svg([105.0, 100.0], color_by_direction=True)
    assert "var(--market-up)" in up and "var(--market-down)" in down
    # 기본값(TA 기존 동작)은 방향 무관 flat이어야 한다 — 회귀 방지
    assert "var(--market-flat)" in spark.sparkline_svg([100.0, 105.0])


# ---------- 설정 정합 ----------

def test_every_strip_key_has_a_history_symbol():
    """타일은 나오는데 미니차트만 조용히 없는 상태를 막는다(실측으로 한 번 발생: wti 누락)."""
    from config.markets import MACRO_HISTORY_SYMBOLS, MACRO_STRIP_GROUPS

    for _, keys in MACRO_STRIP_GROUPS:
        for key in keys:
            assert key in MACRO_HISTORY_SYMBOLS, f"{key}의 이력 심볼이 없다"
