from app.compliance.guard import guard_output
from app.compliance.rules import scan


def test_blocks_buy_sell():
    res = guard_output("지금 삼성전자를 매수하세요. 목표가 9만원입니다.")
    assert res.blocked is True
    assert "buy_sell" in res.categories or "target_price" in res.categories


def test_blocks_return_promise():
    res = guard_output("이 종목은 무조건 20% 수익이 납니다.")
    assert res.blocked is True


def test_allows_educational_with_disclaimer():
    res = guard_output("손절매란 무엇인가에 대한 일반적인 개념을 설명합니다.")
    assert res.blocked is False
    assert "참고자료" in res.text  # 면책 자동 부착


def test_allows_neutral_observation():
    res = guard_output("최근 거래량과 이동평균선 변화 등 관찰 포인트를 정리했습니다.")
    assert res.blocked is False
    assert res.ok is True


def test_scan_whitelist_excludes_education():
    # '손절'이 교육 문맥(란 무엇)과 결합되면 차단 대상이 아님
    hits = scan("손절매란 무엇인가")
    assert all(h.category != "buy_sell" for h in hits)
