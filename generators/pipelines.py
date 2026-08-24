"""공용 데이터 파이프라인 — collectors → validators → repositories → calculators.

**생성기는 외부 소스를 직접 호출하지 않는다**(design/25 Phase B). 모든 도메인의 수집·검증은
여기 모이고, 생성기는 이 모듈이 돌려준 것을 렌더하기만 한다. 각 단계는 runlog로 계측된다
(AI Office의 사실 데이터). collectors가 실행당 메모이즈하므로 한 실행에서 같은 데이터를
두 번 받지 않는다.

Phase B 이전에는 morning/news만 이 계층을 썼고, macro·stock·ta·financials는 같은
"수집→검증→저장" 골격을 각자 생성기 안에 인라인 중복하고 있었다. 그 코드를 **재작성 없이
그대로 옮겨** 왔다 — 동작을 바꾸지 않는 것이 이 단계의 목적이다.

반환값은 도메인별 dict(번들)다. 튜플로 돌려주면 항목이 늘 때마다 모든 호출부가 깨지고,
생성기가 위치로 값을 꺼내야 해서 읽기 어렵다.
"""
from __future__ import annotations

import importlib.util

from calculators import news_categories, news_entities, news_translate
from collectors import (
    dart_collector,
    ecos_collector,
    edgar_collector,
    fred_collector,
    history_collector,
    kiwoom_collector,
    krx_ranking_collector,
    market_collector,
    news_collector,
    ta_collector,
    upbit_collector,
    us_ranking_collector,
)
from config.markets import MACRO_HISTORY_SYMBOLS
from config.settings import DOCS_DIR, NEWS_MAX_TRANSLATE_PER_RUN
from models.market import Quote
from models.news import NewsArticle
from repositories import (
    fs_repository,
    history_repository,
    macro_repository,
    market_repository,
    news_counters,
    news_repository,
    obsidian_repository,
    stock_repository,
    ta_repository,
    translation_cache,
)
from repositories.news_repository import load_store
from repositories.stock_repository import KR_MARKETS
from utils import runlog
from utils.dates import now_kst
from utils.jsonio import load_json, save_json
from validators import fs_validator, macro_validator, market_validator, news_validator, ranking_validator, ta_validator


def get_market() -> dict[str, Quote | None]:
    """시장 8지표: 수집(yahoo/fx + kiwoom 캐시) → 검증 → Quote + market.json."""
    def _collect() -> dict:
        return {**kiwoom_collector.collect(), **market_collector.collect()}

    raw = runlog.run_step("Data Officer", _collect, fallback={}) or {}
    validated = market_validator.validate(raw)
    quotes = market_repository.to_quotes(validated)
    market_repository.persist(quotes)
    return quotes


def get_news() -> list[NewsArticle]:
    """뉴스: 수집 → 검증(중복/결측/타임스탬프) → 모델 병합 → 한글 번역 → 저장 → 카테고리 부여."""
    raw = runlog.run_step("News Research", news_collector.collect, fallback=[]) or []
    validated = news_validator.validate(raw)
    merged = news_repository.merge(news_repository.to_articles(validated))
    # 커밋되는 번역 원장을 먼저 입힌다 — CI는 매 실행이 새 체크아웃이라 gitignored 저장소
    # (cache/)의 번역이 남지 않는다. 이 단계가 없으면 실행마다 최신 40건만 다시 번역하고
    # 그보다 오래된 영어 기사는 영원히 원문으로 남는다(design/24).
    translation_cache.apply_to(merged)
    runlog.run_step(
        "Translator",
        lambda: news_translate.translate_missing(merged, NEWS_MAX_TRANSLATE_PER_RUN),
        fallback=merged,
    )
    translation_cache.save_from(merged)
    # 관련종목 태깅은 **저장 전에** 해야 한다. 종전에는 news 생성기가 저장 뒤에 붙여서
    # 저장소(news_articles.json)의 impact_tags가 늘 비어 있었고, 그 저장소를 읽는
    # get_stock()이 Stock Hub의 "관련 뉴스"를 **전 종목 0건**으로 발행했다(실측: 191개 전부).
    # 뉴스 페이지만 보면 태그가 정상이라 드러나지 않던 결함이다 — 태깅은 한 소비처의 표시
    # 로직이 아니라 기사의 속성이므로 파이프라인이 채워야 한다(번역과 같은 위치).
    news_entities.assign(merged)
    news_repository.save(merged)
    return news_categories.assign(merged)


def get_news_counters(published_ids: set[str]) -> dict:
    """수집된 기사 대비 게재된 기사 카운터.

    `news_collector.collect()`는 실행당 메모이즈되므로 get_news()가 이미 부른 결과를
    그대로 받는다 — 추가 수집은 일어나지 않는다.
    """
    raw = news_collector.collect()
    collected_ids = {r.get("link", "") for r in raw if r.get("link")}
    return news_counters.update(collected_ids, published_ids)


# ── Macro ──────────────────────────────────────────────────────────────────

def _macro_fred() -> dict:
    fallback = {sid: None for sid, _ in fred_collector.SERIES}
    raw = runlog.run_step("Macro FRED", fred_collector.collect, fallback=fallback) or fallback
    out: dict = {}
    for sid, entry in raw.items():
        if not entry:
            out[sid] = None
            continue
        obs = macro_validator.validate_observations(entry.get("observations"))
        out[sid] = {"observations": obs, "next_release": entry.get("next_release")} if obs else None
    return out


def _macro_ecos() -> dict | None:
    raw = runlog.run_step("Macro ECOS", ecos_collector.collect, fallback=None)
    if not raw:
        return None
    obs = macro_validator.validate_observations(raw.get("base_rate"))
    return {"base_rate": obs} if obs else None


def _macro_history() -> dict[str, list[float]]:
    """미니차트 재료. 실패해도 스팟 타일은 그대로 나와야 하므로 폴백은 빈 dict다."""
    return runlog.run_step(
        "Macro History",
        lambda: history_collector.collect(MACRO_HISTORY_SYMBOLS),
        fallback={},
    ) or {}


def get_macro() -> dict:
    """거시 번들 — FRED/ECOS/Upbit 지표 + 경제일정 + 금융시장 스트립.

    `indicators`는 persist가 직전 발행물로 결측을 메운 **병합 결과**다(design/25 Phase A) —
    화면이 이 값을 써야 발행물과 어긋나지 않는다.

    `fred_labels`/`fred_series`/`fred_enabled`는 생성기가 컬렉터 상수를 직접 import하지 않도록
    여기서 실어 보낸다 — Phase C(컬렉터 내부 결합 절단)를 macro 한정으로 미리 달성한 것이다.
    """
    fred_data = _macro_fred()
    ecos_data = _macro_ecos()
    upbit_data = runlog.run_step("Macro Upbit", upbit_collector.collect_btc_krw, fallback=None)
    market = get_market()  # Phase 3 확장 유니버스의 btc/usdkrw 재사용(김치 프리미엄 재료)
    history = _macro_history()

    indicators = macro_repository.build_indicators(fred_data)
    indicators["BOK_BASE_RATE"] = macro_repository.build_base_rate(ecos_data)
    btc = macro_repository.build_btc(upbit_data, market)
    indicators["BTC_KRW"] = btc
    calendar = macro_repository.build_calendar(fred_data)
    # 거래일은 툴팁 전용 부가 정보다 — 결측이면 차트가 날짜 없이 그려질 뿐 실패하지 않는다.
    market_strip = macro_repository.build_market_strip(market, history, history_collector.dates())
    indicators = macro_repository.persist(indicators, calendar, market_strip)

    return {
        "indicators": indicators,
        "calendar_events": calendar["events"],
        "market_strip": market_strip,
        # 라이브 표시(펄스·"n분 전")의 판정 입력 — 발행 시점 기준시각.
        "market_strip_as_of": macro_repository.strip_as_of(market_strip),
        "crypto_line": macro_repository.build_crypto_line(market, btc),
        "fred_labels": dict(fred_collector.SERIES),
        "fred_series": [sid for sid, _ in fred_collector.SERIES],
        "fred_enabled": fred_collector.enabled(),
        "ecos_enabled": ecos_collector.enabled(),
        "has_fred": any(indicators.get(sid) for sid, _ in fred_collector.SERIES),
    }


# ── Technical Analysis ─────────────────────────────────────────────────────

def get_ta() -> dict:
    """KOSPI 일봉 → 검증 → 지표 계산·발행. 재료가 없으면 preview=None(결측 문법)."""
    raw = runlog.run_step("TA Analyst", ta_collector.collect_kospi_daily, fallback=None)
    rows = ta_validator.validate(raw)
    if not rows:
        return {"preview": None, "closes": [], "dates": []}
    body = ta_repository.build(rows)
    ta_repository.persist(body)
    # dates는 closes와 같은 인덱스다 — 차트 x축·툴팁 날짜용(없으면 차트가 날짜 없이 그려진다).
    return {
        "preview": body,
        "closes": [r["close"] for r in rows],
        "dates": [r["date"] for r in rows],
    }


# ── Stock ──────────────────────────────────────────────────────────────────

def _watchlist_rows() -> list[dict]:
    cached = obsidian_repository.load_normalized()
    if not cached:
        return []
    return cached.get("databases", {}).get("watchlist", [])



def _record_ranking_history(kr_rows: list[dict] | None, us_rows: list[dict] | None) -> None:
    """거래일 스냅샷을 히스토리 원장에 축적한다(design/28 Phase A).

    발행물과 달리 이 원장은 재생성이 불가능하므로 랭킹 발행 직후, 다른 어떤 작업보다 먼저
    쓴다 — 뒤따르는 Hub 조립이 실패해도 그날의 과거는 남아야 한다. 마감 전 실행에서는 아무것도
    쓰지 않고 조용히 지나간다(실패가 아니라 정상 흐름이므로 runlog에 에러로 남기지 않는다).
    """
    kr_date = krx_ranking_collector.trade_date() if history_repository.kr_gate_open() else None
    if history_repository.should_record_kr(kr_date):
        history_repository.record("kr", kr_rows, kr_date)

    us_date = us_ranking_collector.trade_date()
    if history_repository.should_record_us(us_date):
        history_repository.record("us", us_rows, us_date)


def get_stock() -> dict:
    """KR/US 랭킹 + 유니버스 + Stock Hub 엔트리까지의 데이터 조립.

    보조 시세 조회(`collect_quotes`)가 유니버스에 의존하므로 유니버스 확정도 여기서 한다 —
    수집 호출을 생성기에 남기지 않으려면 그 선행 계산까지 이 계층이 가져야 한다.
    """
    kr_rows = ranking_validator.validate(
        runlog.run_step("Stock KR Ranking", krx_ranking_collector.collect, fallback=None))
    us_rows = ranking_validator.validate(
        runlog.run_step("Stock US Ranking", us_ranking_collector.collect, fallback=None))

    body = stock_repository.build(kr_rows, us_rows)
    stock_repository.persist(body)

    _record_ranking_history(kr_rows, us_rows)

    universe = stock_repository.build_universe(kr_rows, us_rows, _watchlist_rows())
    save_json(DOCS_DIR / "data" / "stock" / "universe.json",
              [{"code": c, "name": n, "market": m} for c, n, m in universe])

    # 검색 명부(전종목)는 유니버스와 별도 발행물이다 — Financial Statements 검색이 TOP30 컷에
    # 걸리지 않게 한다. 수집은 위 kr_rows/us_rows 재사용이라 추가 호출이 없다.
    save_json(DOCS_DIR / "data" / "stock" / "listing.json",
              stock_repository.build_listing(kr_rows, us_rows))

    # S&P500 후보 밖 US 테마·watchlist 종목(예: TSM, NVO)은 배치 랭킹에 없으므로 보조 조회한다.
    us_covered = {r["code"] for r in (us_rows or [])}
    kr_codes = {r["code"] for r in (kr_rows or [])}
    missing_us = [c for c, _n, m in universe if m not in stock_repository.KR_MARKETS
                  and c not in us_covered and c not in kr_codes]
    supplementary = runlog.run_step(
        "Stock Hub 보조시세", lambda: us_ranking_collector.collect_quotes(missing_us), fallback={},
    )

    # 시장 일정은 macro가 이미 발행한 캘린더를 재사용한다 — Stock이 FOMC 일정을 다시 수집하면
    # 같은 사실의 출처가 둘이 되고 서로 어긋날 수 있다(발행물을 단일 진실로 삼는다).
    calendar = load_json(DOCS_DIR / "data" / "macro" / "calendar.json", default={}) or {}
    hub_entries = stock_repository.build_hub_entries(
        kr_rows, us_rows, universe, supplementary, load_store(),
        calendar_events=calendar.get("events"))
    stock_repository.persist_hub(hub_entries)

    return {"body": body, "universe": universe}


# ── Financial Statements ───────────────────────────────────────────────────

def _fs_universe() -> list[dict]:
    data = load_json(DOCS_DIR / "data" / "stock" / "universe.json", default=[])
    return data if isinstance(data, list) else []


def _fs_close_price(code: str) -> float | None:
    hub = load_json(DOCS_DIR / "data" / "stock" / "hub" / f"{code}.json", default=None)
    if not hub or not hub.get("quote"):
        return None
    return hub["quote"].get("close")


def _fs_build_kr(entries: list[dict]) -> None:
    corp_codes = runlog.run_step("FS DART corpCode", dart_collector.collect_corp_codes, fallback=None)
    year = now_kst().year
    for e in entries:
        raw = None
        corp_code = (corp_codes or {}).get(e["code"])
        if corp_code:
            raw = dart_collector.collect_financials(corp_code, year)
        financials = fs_validator.validate(raw)
        body = fs_repository.build(e["code"], e["name"], e["market"], financials,
                                   _fs_close_price(e["code"]), "dart")
        fs_repository.persist(e["code"], body)


def _fs_build_us(entries: list[dict]) -> None:
    cik_map = runlog.run_step("FS EDGAR CIK맵", edgar_collector.collect_cik_map, fallback=None)
    for e in entries:
        raw = None
        cik = (cik_map or {}).get(e["code"])
        if cik:
            raw = edgar_collector.collect_company_facts(cik)
        financials = fs_validator.validate(raw)
        body = fs_repository.build(e["code"], e["name"], e["market"], financials,
                                   _fs_close_price(e["code"]), "edgar")
        fs_repository.persist(e["code"], body)


def get_asset_raw() -> dict:
    """4계좌 원장 수집(데스크톱 전용 Kiwoom 포함) — 정규화·집계·암호화는 생성기/리포지터리 몫.

    Kiwoom은 32-bit OCX(Windows 데스크톱 세션) 없이는 조회 불가하므로 CI에서는 그 계좌만
    결측이 되고 나머지(KIS·BYBIT)는 정상 수집된다(부분 실패 허용).
    반환 dict를 그대로 발행하면 안 된다 — 계좌 절대금액이 담긴 평문이다.
    """
    from collectors import bybit_collector, kis_collector

    # Kiwoom은 **시도할 수 있는 환경에서만** 기록한다. CI에서도 completed로 남기면
    # runlog의 last_run이 매일 갱신돼, 데스크톱이 며칠 안 돌아도 센서가 신선하다고 판정한다
    # (design/28 — 수집 주체 분리의 부작용). 기록하지 않으면 runlog 병합이 데스크톱의
    # 마지막 기록을 보존하므로, 신선도 규칙이 키움 데이터의 진짜 나이를 잰다.
    kiwoom = runlog.run_step("Asset Kiwoom", _asset_kiwoom_balance, fallback=None) \
        if _kiwoom_available() else None

    return {
        "kiwoom": kiwoom,
        "kis_foreign": runlog.run_step(
            "Asset KIS 위탁", kis_collector.collect_overseas_balance, fallback=None),
        "kis_isa": runlog.run_step(
            "Asset KIS ISA", kis_collector.collect_isa_balance, fallback=None),
        "bybit": runlog.run_step(
            "Asset BYBIT", bybit_collector.collect_wallet_balance, fallback=None),
    }


def _kiwoom_available() -> bool:
    """Kiwoom OCX를 시도해 볼 수 있는 환경인가(32bit Windows + PyQt5 + OCX).

    설치 여부로만 판정한다 — 로그인 성공까지 보지 않는다. 시도했다가 실패한 것은
    '기록해야 할 장애'이고, 애초에 시도조차 불가능한 환경(CI 리눅스)은 '기록할 사건이 아님'이다.
    이 구분이 있어야 센서가 데스크톱 미실행을 정확히 잡는다.

    **PyQt5를 직접 본다.** `collectors.kiwoom_desktop.api`는 PyQt5를 함수 안에서 지연 import
    하므로 그 모듈의 임포트 성공은 아무것도 보장하지 않는다 — CI에서도 성공한다(실측).
    requirements의 PyQt5는 `platform_system == 'Windows'` 마커가 붙어 있어, 설치 여부가
    곧 "OCX를 시도할 수 있는 환경인가"와 같다.
    """
    return importlib.util.find_spec("PyQt5") is not None


def _asset_kiwoom_balance() -> dict | None:
    """키움 잔고 — app/sync.py가 등록한 공유 세션을 우선 재사용(로그인 1회 원칙)."""
    from utils.logging import get_logger

    log = get_logger("pipelines.asset")
    try:
        from collectors.kiwoom_desktop import api as kiwoom_api
        from collectors.kiwoom_desktop.account import fetch_balance, list_accounts
    except Exception as exc:  # noqa: BLE001 - PyQt5/OCX 임포트 자체가 없는 환경(CI 등)
        log.info("Kiwoom 모듈 사용 불가(비-Windows 환경 등): %s", exc)
        return None

    api = kiwoom_api.shared()
    if api is None:
        # 공유 세션 없음 = 단독 CLI 빌드. 자체 로그인을 시도하되, 데스크톱 세션이 없는
        # 환경(CI 등)에서는 이 계좌만 결측으로 남기고 나머지 3계좌 수집을 계속한다.
        try:
            api = kiwoom_api.KiwoomAPI()
        except kiwoom_api.KiwoomError as exc:
            log.info("Kiwoom 미가용(데스크톱 세션 없음): %s", exc)
            return None
        if not api.connect():
            log.warning("Kiwoom 로그인 실패")
            return None

    accounts = list_accounts(api)
    if not accounts:
        return None
    return fetch_balance(api, accounts[0])


def get_financials() -> dict:
    """유니버스 종목별 재무 카드 발행. KR=DART(키 필요) · US=EDGAR(키 불필요)."""
    universe = _fs_universe()
    kr_entries = [e for e in universe if isinstance(e, dict) and e.get("market") in KR_MARKETS]
    us_entries = [e for e in universe if isinstance(e, dict) and e.get("market") not in KR_MARKETS]

    _fs_build_kr(kr_entries)
    _fs_build_us(us_entries)

    save_json(DOCS_DIR / "data" / "financials" / "index.json", _fs_published_cards())
    return {"universe": universe}


def _fs_published_cards() -> list[dict]:
    """발행 디렉터리에 **실제로 존재하는** 카드 목록.

    유니버스를 그대로 적으면 실제와 어긋난다 — 유니버스는 거래대금 순위에 따라 매일 바뀌는데
    지난 발행분은 지워지지 않고 남기 때문이다(실측 2026-08-17: 유니버스 71 vs 파일 162).
    검색 화면이 이 목록으로 "재무 미수집" 표시를 결정하므로, 있는 카드를 없다고 하면 그대로
    거짓말이 된다. 디렉터리를 읽는 편이 유일하게 정직하다.
    """
    out: list[dict] = []
    for path in sorted((DOCS_DIR / "data" / "financials").glob("*.json")):
        if path.stem == "index":
            continue
        body = load_json(path, default=None)
        if isinstance(body, dict) and body.get("code"):
            out.append({"code": body["code"], "name": body.get("name") or body["code"],
                        "market": body.get("market") or ""})
    return out
