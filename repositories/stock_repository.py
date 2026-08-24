"""KR/US 랭킹 원장 → rankings.json 컨테이너 + 종목 유니버스 병합(design/20 Phase 7, design/21 §7-1·§8).

미국 population은 전체 시장이 아니라 랭킹 후보 유니버스(config/universe.US_CANDIDATE_LISTING)
크기다 — "미국 전시장 TOP30 무료 불가" 제약을 모집단 캡션으로 정직하게 고지한다(design/21 §8).
마감 EOD 스냅샷(design/21 §225)이라 session_key="none"(세션 무관 배치, ta_repository와 동일 원칙).
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators.ranking_calculator import theme_of, top_n
from config.freshness import THRESHOLDS
from config.settings import DOCS_DIR
from config.themes import THEMES
from config.universe import RANKING_TOP_N, WATCHLIST_MARKET_KEYS, WATCHLIST_TICKER_KEYS
from utils.jsonio import save_json

_FRESH_MAX_MIN, _STALE_MIN_MIN = THRESHOLDS["stock_ranking"]
_EXPECTED_T_MIN = 24 * 60


def _table(rows: list[dict] | None, session_key: str) -> dict | None:
    """수집 실패(rows=None)면 카드째 생략(결측 문법) — 가짜 0행 테이블을 만들지 않는다."""
    if not rows:
        return None
    return {
        "population": len(rows),
        "as_of_iso": datetime.now(timezone.utc).isoformat(),
        "session_key": session_key,
        "expected_T_min": _EXPECTED_T_MIN,
        "rows": top_n(rows, RANKING_TOP_N),
    }


def build(kr_rows: list[dict] | None, us_rows: list[dict] | None) -> dict:
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "kr": _table(kr_rows, "none"),
        "us": _table(us_rows, "none"),
    }


def _first_present(row: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = row.get(k)
        if v:
            return str(v)
    return None


def build_universe(
    kr_rows: list[dict] | None,
    us_rows: list[dict] | None,
    watchlist_rows: list[dict] | None = None,
) -> list[tuple[str, str, str]]:
    """유니버스 = TOP30×2 ∪ 테마 종목 ∪ vault 워치리스트(design/21 §8). (code, name, market) 중복 제거.

    Stock Hub/Financials/Portfolio가 "유니버스 내 종목인가"를 판정할 때 이 목록의 code 집합을 쓴다.
    """
    seen: dict[str, tuple[str, str, str]] = {}

    def _add(code: str | None, name: str, market: str) -> None:
        if code and code not in seen:
            seen[code] = (code, name, market)

    for r in (top_n(kr_rows, RANKING_TOP_N) if kr_rows else []):
        _add(r["code"], r["name"], r["market"])
    for r in (top_n(us_rows, RANKING_TOP_N) if us_rows else []):
        _add(r["code"], r["name"], "US")
    for stocks in THEMES.values():
        for code, name, market in stocks:
            _add(code, name, market)
    for row in (watchlist_rows or []):
        code = _first_present(row, WATCHLIST_TICKER_KEYS)
        market = _first_present(row, WATCHLIST_MARKET_KEYS) or ""
        if code:
            _add(code, code, market)

    return list(seen.values())


def build_listing(kr_rows: list[dict] | None, us_rows: list[dict] | None) -> list[dict]:
    """검색 명부 = 수집된 **전종목**(KR 전 시장 ∪ US 후보). 유니버스(카드 발행 대상)와 다르다.

    유니버스는 거래대금 TOP30 컷이 있어 삼천당제약(143위)·두산로보틱스(106위) 같은 종목이
    검색조차 되지 않았다(2026-08-17 실측). 그런데 KRX 스냅샷은 애초에 전종목 2,872건을 한 번에
    받아오므로, 명부를 따로 발행하는 데 드는 수집 비용은 0이다 — 발행물 하나 늘리는 것뿐이다.

    카드(재무 JSON)까지 전종목으로 늘리지는 않는다. 그건 종목당 DART 호출 1회라 비용이 다르다.
    명부에 있으나 카드가 없는 종목은 상세에서 "준비되지 않음" 빈 상태로 정직하게 처리한다.

    정렬은 거래대금 내림차순 — 검색 결과를 상위 N건으로 자를 때 "삼성"이 삼성전자부터 나오게
    한다. KR·US는 통화가 달라 서로 비교할 수 없으므로 섞지 않고 KR 다음 US로 이어 붙인다.
    """
    def _sorted(rows: list[dict] | None) -> list[dict]:
        return sorted(rows or [], key=lambda r: r.get("amount") or 0, reverse=True)

    seen: dict[str, dict] = {}
    for r in _sorted(kr_rows):
        if r.get("code") and r["code"] not in seen:
            seen[r["code"]] = {"code": r["code"], "name": r.get("name") or r["code"],
                               "market": r.get("market") or ""}
    for r in _sorted(us_rows):
        if r.get("code") and r["code"] not in seen:
            seen[r["code"]] = {"code": r["code"], "name": r.get("name") or r["code"], "market": "US"}
    return list(seen.values())


# FDR 랭킹은 "KOSPI"/"KOSDAQ"/"KONEX"/"KOSDAQ GLOBAL"을 쓰고, config/themes.py·config/entities.py는
# 기존 관례대로 일반 라벨 "KRX"를 쓴다(둘 다 한국 종목이므로 이 집합에서 동일하게 취급한다).
KR_MARKETS = {"KOSPI", "KOSDAQ", "KONEX", "KOSDAQ GLOBAL", "KRX"}


def _tradingview_symbol(code: str, market: str) -> str | None:
    """design/05 §3-2 C — TradingView 딥링크 심볼. 미국은 정확한 거래소(NASDAQ/NYSE) 프리픽스를
    확정할 무료 소스가 없어(design/21 §225와 동일한 제약) 베어 티커로 대체한다(정직한 근사)."""
    if market in KR_MARKETS:
        return f"KRX:{code}"
    if code:
        return code
    return None


def _quote_from_row(row: dict | None, session_key: str) -> dict | None:
    if not row:
        return None
    return {
        "close": row["close"],
        "change_pct": row.get("change_pct"),
        "volume": row.get("volume"),
        "amount": row.get("amount"),
        "marcap": row.get("marcap"),
        "as_of_iso": datetime.now(timezone.utc).isoformat(),
        "session_key": session_key,
    }


def upcoming_market_events(events: list[dict] | None, limit: int = 4) -> list[dict]:
    """다가오는 **시장** 일정(FOMC 등) — 아직 지나지 않은 것만 시간순 limit건.

    design/04 §3-5 D블록은 "다가오는 일정"을 요구하지만, 종목별 일정(실적발표일·배당기준일)은
    무료 소스가 없다. 없는 것을 지어내는 대신, 어느 종목을 보든 실제로 영향을 받는 거시 일정을
    **"시장 일정"이라고 정직하게 라벨링해서** 채운다 — 종목 고유 일정인 척하지 않는다.
    """
    if not events:
        return []
    now = datetime.now(timezone.utc)
    upcoming = []
    for e in events:
        at = e.get("event_at_utc")
        if not at:
            continue
        try:
            when = datetime.fromisoformat(at)
        except (ValueError, TypeError):
            continue
        if when >= now:
            upcoming.append((when, {"date": e.get("date"), "label": e.get("label"),
                                    "source": e.get("source")}))
    upcoming.sort(key=lambda p: p[0])
    return [item for _when, item in upcoming[:limit]]


def build_hub_entries(
    kr_rows: list[dict] | None,
    us_rows: list[dict] | None,
    universe: list[tuple[str, str, str]],
    supplementary_us_quotes: dict[str, dict] | None,
    articles: list,
    calendar_events: list[dict] | None = None,
) -> dict[str, dict]:
    """유니버스 각 종목의 Stock Hub 단건 요약(design/05). 시세 없는 종목은 quote=None(결측 문법) —
    유니버스 밖("파일 자체가 없음")과 "유니버스 내이나 시세 미확보"를 구분하기 위해서다.
    """
    market_events = upcoming_market_events(calendar_events)
    kr_by_code = {r["code"]: r for r in (kr_rows or [])}
    us_by_code = {r["code"]: r for r in (us_rows or [])}
    supplementary_us_quotes = supplementary_us_quotes or {}

    entries: dict[str, dict] = {}
    for code, name, market in universe:
        if market in KR_MARKETS:
            quote = _quote_from_row(kr_by_code.get(code), "none")
        else:
            row = us_by_code.get(code) or supplementary_us_quotes.get(code)
            quote = _quote_from_row(row, "none") if row else None

        # 제목은 번역본 우선 — 뉴스 페이지와 같은 규칙이다(design/24). Hub만 원문을 쓰면
        # 같은 기사가 화면마다 다른 언어로 보인다.
        related = [
            {"title": a.title_ko or a.title, "link": a.link, "source": a.source,
             "published": a.published.isoformat() if a.published else None}
            for a in articles
            if any(t.get("ticker") == code for t in a.impact_tags)
        ][:5]

        entries[code] = {
            "code": code,
            "name": name,
            "market": market,
            "theme": theme_of(code),
            "quote": quote,
            "tradingview_symbol": _tradingview_symbol(code, market),
            "related_news": related,
            "market_events": market_events,
        }
    return entries


def persist_hub(entries: dict[str, dict]) -> None:
    for code, body in entries.items():
        save_json(DOCS_DIR / "data" / "stock" / "hub" / f"{code}.json", body)


def persist(body: dict) -> None:
    save_json(DOCS_DIR / "data" / "stock" / "rankings.json", body)


def freshness_attrs() -> dict:
    return {"fresh_max_min": _FRESH_MAX_MIN, "stale_min_min": _STALE_MIN_MIN}
