"""키워드 매칭 단일 규칙 — 카테고리·테마·관련종목이 공유한다(design/24 N3).

**왜 필요한가.** 종전에는 세 곳이 각자 `keyword in text` 부분문자열 매칭을 했다. 짧은 영문
키워드가 무관한 단어에 묻어 걸려 집계가 무너졌다(실측 400건 코퍼스):

    "ai"  67건 → 실제 30건   ("said" 11 · "chain" 4 · "ukraine" 3 · "retailer" 3 · "straight" 2)
    "ppi"  3건 → 실제  0건   ("shopping" 2 · "topping" 1)   ← 전부 오탐
    "chip" 5건 → 실제  4건   ("chipotle" 2)
    "kai"  2건 → 실제  1건   ("alakai" 1)

**왜 그냥 `\\b`를 쓰지 않는가.** 파이썬 `re`의 `\\b`는 유니코드 인식이라 한글도 단어 문자로
본다. 그러면 `"ai주"`(AI 관련주)·`"ai로"`처럼 **한글 조사가 붙은 정탐**이 경계 없음으로
판정돼 통째로 탈락한다(실측에서 `ai주` 6회 · `ai로` 2회). 같은 이유로 `"플러스fomc와"`처럼
공백 없이 한글에 붙은 표기도 살려야 한다.

그래서 경계를 **ASCII 영숫자에 한정**한다 — 앞뒤가 `[a-z0-9]`가 아니면 경계로 인정한다.
한글은 경계로 취급되므로 조사가 붙어도 매칭되고, 영어 단어 속에 묻힌 경우만 걸러진다.

**한글 키워드는 부분문자열 그대로.** 한국어는 교착어라 "반도체가·반도체를·반도체株"처럼
붙어 활용되며, 경계를 요구하면 정탐을 잃는다. 오탐 실측에서도 한글 키워드는 문제가 없었다.
"""
from __future__ import annotations

import re
from functools import lru_cache

# 영문 키워드에 허용하는 굴절형 — 복수형까지만. "chipmaker"류 합성어는 정규식으로 풀면
# "chipotle"까지 통과하므로(어휘 문제이지 형태 문제가 아니다) config/keywords.py에 표제어로
# 명시해 등록한다 — 무엇이 잡히는지 사전만 보면 알 수 있게 유지하는 편이 안전하다.
def _forms(keyword: str) -> list[str]:
    forms = {keyword, keyword + "s", keyword + "es"}
    if keyword.endswith("y"):
        forms.add(keyword[:-1] + "ies")
    return sorted(forms, key=len, reverse=True)  # 긴 형태 우선(정규식 대안 선택 규칙)


@lru_cache(maxsize=2048)
def _pattern(keyword: str) -> re.Pattern | None:
    """ASCII 키워드용 경계 정규식. 한글이 섞인 키워드는 None(부분문자열 매칭)."""
    if not keyword.isascii():
        return None
    alts = "|".join(re.escape(f) for f in _forms(keyword))
    return re.compile(rf"(?<![a-z0-9])(?:{alts})(?![a-z0-9])")


def matches(keyword: str, text: str) -> bool:
    """text(소문자여야 함)에 keyword가 의미 있게 등장하는가."""
    pattern = _pattern(keyword)
    return keyword in text if pattern is None else pattern.search(text) is not None


def any_match(keywords, text: str) -> bool:
    return any(matches(k, text) for k in keywords)


def text_of(*parts: str) -> str:
    """매칭 대상 텍스트 조립(소문자화) — 세 호출부가 같은 방식으로 만들도록 한곳에 둔다."""
    return " ".join(p for p in parts if p).lower()
