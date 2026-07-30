"""키워드 매칭 규칙 — 영문 단어경계 + 한글 부분문자열(design/24 N3).

실측 400건 코퍼스에서 나온 실제 오탐/정탐 사례를 그대로 케이스로 굳혔다. 특히
"한글 조사가 붙은 영문 키워드"(ai주·ai로)는 파이썬 `\\b`를 쓰면 사라지는 정탐이라
이 테스트가 그 회귀를 막는 유일한 방어선이다.
"""
from __future__ import annotations

import pytest

from calculators import keyword_match
from calculators.news_categories import categorize
from calculators.news_entities import extract_impact_tags
from calculators.themes import extract_themes
from models.news import NewsArticle


def m(kw: str, text: str) -> bool:
    return keyword_match.matches(kw, keyword_match.text_of(text))


# ---------- 실측 오탐: 영어 단어에 묻혀 걸리던 것들 ----------

@pytest.mark.parametrize("host", ["said", "chain", "ukraine", "retailer", "straight", "against"])
def test_ai_no_longer_matches_english_words(host):
    """'ai' 67건 중 37건이 이런 단어 때문이었다(실측 최대 오탐원)."""
    assert not m("ai", f"Company {host} something today")


@pytest.mark.parametrize("kw,host", [
    ("ppi", "shopping"),   # ppi는 실측 3건이 전부 오탐이었다
    ("ppi", "topping"),
    ("chip", "chipotle"),
    ("kai", "alakai"),
])
def test_short_keywords_no_longer_match_hosts(kw, host):
    assert not m(kw, f"the {host} report")


# ---------- 정탐: 경계를 넣어도 반드시 살아야 하는 것들 ----------

@pytest.mark.parametrize("text", [
    "AI 반도체 수요 급증",      # 공백 구분
    "AI주 강세 지속",           # 한글 조사 — \\b를 쓰면 사라진다(실측 6회)
    "AI로 만든 서비스",         # 실측 2회
    "AI-driven rally",          # 하이픈
    "generative ai.",           # 문장부호
    "AI, 반도체",
])
def test_ai_still_matches_real_usages(text):
    assert m("ai", text)


def test_ascii_keyword_glued_to_hangul_still_matches():
    """'플러스fomc와' — 공백 없이 한글에 붙은 표기(실측 1회)."""
    assert m("fomc", "코스피플러스fomc와 금리")


def test_english_plurals_are_covered():
    assert m("chip", "memory chips demand")
    assert m("robot", "humanoid robots")


def test_y_ending_plural_is_covered():
    assert m("foundry", "advanced foundries expand")


def test_compound_registered_as_headword_matches():
    """'chipmaker'는 정규식이 아니라 사전 등록으로 잡는다(그래야 chipotle이 안 딸려온다)."""
    assert m("chipmaker", "the chipmaker raised guidance")
    assert not m("chip", "chipotle earnings")


# ---------- 한글은 교착어라 부분문자열 유지 ----------

@pytest.mark.parametrize("text", ["반도체가 오른다", "반도체를 샀다", "반도체株 강세"])
def test_korean_keyword_matches_with_particles(text):
    assert m("반도체", text)


# ---------- 통합: 세 호출부가 같은 규칙을 쓴다 ----------

def _art(title: str, region: str = "US") -> NewsArticle:
    return NewsArticle(title=title, link="http://x/1", region=region, summary="")


def test_categorize_does_not_tag_ai_for_said():
    assert "ai" not in categorize(_art("Analyst said stocks will rise"))


def test_categorize_still_tags_ai_for_real_article():
    assert "ai" in categorize(_art("AI chip demand surges"))


def test_categorize_macro_keeps_federal_reserve():
    """'fed'에 경계를 넣으면 'Federal Reserve'를 놓친다 — 표제어로 보강했다(실측 6회)."""
    assert "macro" in categorize(_art("Federal Reserve holds rates steady"))


def test_themes_no_longer_inflated_by_said():
    arts = [_art(f"Official said something {i}") for i in range(20)]
    assert extract_themes(arts) == []


def test_entities_do_not_match_inside_words():
    """'meta' → 'metal/metaverse' 같은 오탐 방지(관련종목 칩은 오탐이 특히 눈에 띈다)."""
    tags = extract_impact_tags(_art("Metal prices climb on supply squeeze"))
    assert [t for t in tags if t["ticker"] == "META"] == []


def test_entities_still_match_normal_mention():
    tags = extract_impact_tags(_art("Meta reports strong ad revenue"))
    assert any(t["ticker"] == "META" for t in tags)
