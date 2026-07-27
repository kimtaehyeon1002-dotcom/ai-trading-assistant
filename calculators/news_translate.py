"""영어 기사 한글 번역 — 원문은 링크로만 남기고, 표시는 번역본을 최우선으로 한다(design/24).

무료 비공식 Google 번역 엔드포인트(deep-translator, API 키 불필요)를 쓴다. no-AI 원칙(design/21)은
"판단·생성을 지어내지 않는다"는 뜻이지 기계적 언어 변환까지 막는 것은 아니다 — 원문 사실을
그대로 옮기는 번역은 요약(추출)과 같은 층위의 사실 가공으로 취급한다.

실패(네트워크·차단 등)는 원문 폴백으로 조용히 넘어간다 — 지어낸 번역을 넣느니 원문이 낫다.
"""
from __future__ import annotations

from models.news import NewsArticle
from utils.logging import get_logger

log = get_logger("calculators.news_translate")


def _translate(text: str) -> str | None:
    """text(영어) → 한글. 빈 문자열은 번역할 것이 없으니 그대로 반환. 실패는 None."""
    if not text or not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator

        result = GoogleTranslator(source="en", target="ko").translate(text)
        return result.strip() if result else None
    except Exception as exc:  # noqa: BLE001 - 미설치·네트워크·차단 전부 원문 폴백으로 흡수
        log.warning("번역 실패(원문 유지): %s", exc)
        return None


def translate_missing(articles: list[NewsArticle], limit: int) -> list[NewsArticle]:
    """lang != 'ko'이고 아직 번역 안 된 기사만, 실행당 최대 limit건 번역(제자리 수정).

    제목·요약을 하나로 묶어 번역해야 캐시가 온전하다 — 제목만 성공하고 요약이 실패하면
    "제목은 한글, 요약은 영어"인 어색한 반쪽 상태가 영구 고착된다(요약이 실패하면 title_ko도
    None으로 되돌려 다음 실행에 통째로 재시도한다).
    """
    attempted = 0
    for a in articles:
        if a.lang == "ko" or a.title_ko:
            continue
        if attempted >= limit:
            break
        attempted += 1

        title_ko = _translate(a.title)
        if title_ko is None:
            continue  # 제목 실패 — 다음 실행 재시도
        summary_ko = _translate(a.summary) if a.summary.strip() else ""
        if a.summary.strip() and summary_ko is None:
            continue  # 요약만 실패 — 부분 캐시를 남기지 않고 통째로 재시도

        a.title_ko = title_ko
        a.summary_ko = summary_ko
    return articles
