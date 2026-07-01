from models.news import NewsArticle
from services.news.categorize import categorize


def test_kr_semiconductor():
    a = NewsArticle(title="삼성전자 HBM 반도체 신제품 공개", link="http://x/1", region="KR", summary="")
    cats = categorize(a)
    assert "kr_market" in cats and "semiconductor" in cats


def test_us_macro():
    a = NewsArticle(title="Fed rate decision amid inflation", link="http://x/2", region="US", summary="")
    cats = categorize(a)
    assert "us_market" in cats and "macro" in cats


def test_ai():
    a = NewsArticle(title="OpenAI unveils new GPT model", link="http://x/3", region="US", summary="")
    assert "ai" in categorize(a)


def test_no_breaking_when_no_time():
    a = NewsArticle(title="일반 시황", link="http://x/4", region="KR", published=None)
    assert "breaking" not in categorize(a)
