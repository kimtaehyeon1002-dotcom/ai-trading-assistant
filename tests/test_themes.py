from models.news import NewsArticle
from calculators.themes import extract_themes


def _a(i: int, title: str, summary: str = "") -> NewsArticle:
    return NewsArticle(title=title, link=f"http://x/{i}", summary=summary, region="KR")


def test_top3_by_frequency():
    arts = [
        _a(1, "엔비디아 HBM 반도체 수요 급증"),
        _a(2, "삼성전자 파운드리 수주"),
        _a(3, "SK하이닉스 HBM 공급 확대"),
        _a(4, "AI 인공지능 투자 확대"),
        _a(5, "생성형 AI 시장 성장"),
        _a(6, "한화에어로 방산 수출"),
        _a(7, "국제유가 변동, 에너지 시장"),
    ]
    themes = extract_themes(arts, top_n=3)
    names = [t["name"] for t in themes]
    assert len(themes) == 3
    assert names[0] == "반도체"  # 3건으로 최다
    assert "AI" in names
    assert all(t["count"] > 0 and t["sample"] for t in themes)


def test_no_fabricated_themes():
    # 매칭되는 뉴스가 없으면 빈 리스트(테마 조작 금지)
    assert extract_themes([_a(1, "오늘 날씨 맑음")]) == []
    assert extract_themes([]) == []


def test_top_n_limit():
    arts = [_a(i, t) for i, t in enumerate(
        ["반도체", "AI 인공지능", "방산 무기", "원전 수출", "배터리 2차전지"])]
    assert len(extract_themes(arts, top_n=3)) == 3
