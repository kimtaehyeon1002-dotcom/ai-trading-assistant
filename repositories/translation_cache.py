"""뉴스 번역 캐시 — CI 실행 간에 살아남는 공유 원장(design/24).

왜 별도 파일인가: 기사 저장소(cache/news_articles.json)는 `/cache/`라 **gitignored**다.
CI(GitHub Actions)는 매 실행이 새 체크아웃이므로 그 저장소가 늘 비어 있고, 번역 결과도
실행이 끝나면 통째로 버려졌다. 그래서 매번 "가장 최근 40건"만 다시 번역하고 그보다 오래된
영어 기사는 **영원히 번역되지 않았다**(실제 증상: 배포 페이지 us_market 30건 중 11건이
영어 원문 — 전부 목록 하위의 오래된 기사).

data/cache/는 데스크톱↔CI 전달용으로 커밋되는 디렉터리(config/settings.py DATA_CACHE_DIR)라
여기에 두면 번역이 실행 간에 누적된다 — 한 번 번역한 기사는 다시 번역하지 않는다.

CI와 데스크톱이 함께 쓰는 원장이므로 저장은 **항상 병합**이다(통째로 덮어쓰면 상대가 쌓은
번역이 유실된다 — runlog.json에서 같은 사고가 있었다).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config.settings import DATA_CACHE_DIR
from models.news import NewsArticle
from utils.jsonio import load_json, save_json
from utils.logging import get_logger

log = get_logger("repositories.translation_cache")

_CACHE = DATA_CACHE_DIR / "news_translations.json"

# 보관 상한 — 기사 저장소(400건)보다 넉넉히 잡는다. RSS 창에서 잠시 빠졌다 돌아오는 기사의
# 번역을 버리지 않기 위함이며, 넘치면 오래 안 쓰인 항목부터 버린다(seen_at 기준).
MAX_ENTRIES = 1500


def load() -> dict[str, dict]:
    """{article_id: {"title_ko": str, "summary_ko": str, "seen_at": iso}}."""
    data = load_json(_CACHE, default={}) or {}
    return data if isinstance(data, dict) else {}


def apply_to(articles: list[NewsArticle]) -> int:
    """캐시에 있는 번역을 기사에 채운다(제자리 수정) → 채운 건수.

    이미 번역이 붙어 있는 기사는 건드리지 않는다(로컬 저장소 경유분이 우선).
    """
    cache = load()
    filled = 0
    for a in articles:
        if a.lang == "ko" or a.title_ko:
            continue
        hit = cache.get(a.id)
        if isinstance(hit, dict) and hit.get("title_ko"):
            a.title_ko = hit["title_ko"]
            a.summary_ko = hit.get("summary_ko", "")
            filled += 1
    if filled:
        log.info("번역 캐시 적용: %d건(재번역 회피)", filled)
    return filled


def save_from(articles: list[NewsArticle]) -> None:
    """기사에 붙은 번역을 캐시에 병합 저장한다(기존 항목 보존)."""
    cache = load()
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for a in articles:
        if not a.title_ko:
            continue
        if a.id not in cache:
            added += 1
        cache[a.id] = {"title_ko": a.title_ko,
                       "summary_ko": a.summary_ko or "",
                       "seen_at": now}
    if len(cache) > MAX_ENTRIES:  # 오래된 항목부터 정리
        newest = sorted(cache.items(), key=lambda kv: kv[1].get("seen_at", ""), reverse=True)
        cache = dict(newest[:MAX_ENTRIES])
    try:
        save_json(_CACHE, cache)
        if added:
            log.info("번역 캐시 신규 저장 %d건(총 %d건)", added, len(cache))
    except OSError as exc:
        log.warning("번역 캐시 저장 실패(빌드는 계속): %s", exc)
