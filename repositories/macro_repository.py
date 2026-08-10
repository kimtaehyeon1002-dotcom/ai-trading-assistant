"""검증된 거시 관측치 → Envelope 빌드 + docs/data/macro/{indicators,calendar}.json 기록.

Envelope의 change_abs/change_pct는 직전 관측치 대비(전월비 등) 변화이며, 전년동월비(YoY)는
별도 "yoy" 필드로 분리한다(design/20 Phase 6, calculators/macro_indicators.yoy_change 사용).
as_of_iso는 관측 대상 기간이 아니라 "이 값이 마지막으로 확인된 시각"(수집/빌드 시각)이다 —
발표 주기가 불규칙한 지표 특성상 이렇게 해야 "재확인한 지 얼마나 됐는가"를 정직하게 반영한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from calculators.macro_indicators import kimchi_premium_pct, yoy_change
from collectors.fred_collector import SERIES as FRED_SERIES
from config.consensus import CONSENSUS
from config.economic_calendar import FOMC_2026, FOMC_STATEMENT_TIME_ET
from config.freshness import THRESHOLDS
from config.markets import ENVELOPE_META, MACRO_CRYPTO_KEYS, MACRO_STRIP_GROUPS
from config.settings import DOCS_DIR
from utils import domain_cache, sparkline as spark
from utils.jsonio import save_json

_FRESH_MAX_MIN, _STALE_MIN_MIN = THRESHOLDS["macro"]

# 스트립 미니차트가 그리는 봉 개수(design/25 §10). 3개월(약 63봉)을 200px에 욱여넣으면
# 봉당 3px라 선이 뭉개진다 — 실측에서 60포인트/147px = 2.4px였고 그게 "가시성이 떨어진다"의
# 실체였다. 한 달(약 22거래일)이면 봉당 9px로 궤적이 또렷하고, "지금 세계가 어떻게 돌아가는가"
# 라는 이 페이지의 질문에도 한 달이 맞는 창이다. 수집은 3개월 그대로 두어 나중에 창을 넓힐 수 있다.
STRIP_CHART_POINTS = 22
STRIP_CHART_WINDOW_LABEL = "최근 1개월"
_EXPECTED_T_MIN = 60
_LABELS = dict(FRED_SERIES)


def _envelope(as_of: str, value: float, change_abs, change_pct, label: str) -> dict:
    return {
        "value": value,
        "change_abs": change_abs,
        "change_pct": change_pct,
        "unit": "%" if change_pct is not None and abs(value) < 100 else "pt",
        "as_of_iso": as_of,
        "source": "fred",
        "session_key": "none",
        "expected_T_min": _EXPECTED_T_MIN,
        "freshness_basis": "as_of",
        "label": label,
    }


def build_indicators(fred_data: dict[str, dict | None]) -> dict:
    """fred_data: fred_collector.collect() 형태 {series_id: {'observations','next_release'}|None}."""
    as_of = datetime.now(timezone.utc).isoformat()
    out: dict = {}
    for series_id, label in FRED_SERIES:
        entry = fred_data.get(series_id)
        if not entry or not entry.get("observations"):
            out[series_id] = None
            continue
        obs = entry["observations"]
        latest = obs[-1]
        prior = obs[-2] if len(obs) >= 2 else None
        change_abs = round(latest["value"] - prior["value"], 4) if prior else None
        change_pct = round((latest["value"] / prior["value"] - 1) * 100, 2) if prior and prior["value"] else None

        item: dict = {
            "envelope": _envelope(as_of, latest["value"], change_abs, change_pct, label),
            "yoy": yoy_change(obs),
            "next_release": entry.get("next_release"),
        }
        if series_id in CONSENSUS:
            item["consensus"] = CONSENSUS[series_id]
        out[series_id] = item
    return out


def build_base_rate(ecos_data: dict | None) -> dict | None:
    """ecos_collector.collect() 결과 → Envelope 래퍼. 재료 없으면 None(결측 문법)."""
    if not ecos_data or not ecos_data.get("base_rate"):
        return None
    obs = ecos_data["base_rate"]
    latest, prior = obs[-1], (obs[-2] if len(obs) >= 2 else None)
    change_abs = round(latest["value"] - prior["value"], 4) if prior else None
    as_of = datetime.now(timezone.utc).isoformat()
    env = _envelope(as_of, latest["value"], change_abs, None, "한국은행 기준금리")
    env["unit"], env["source"] = "%", "ecos"
    return {"envelope": env, "yoy": None, "next_release": None}


def build_btc(upbit_data: dict | None, market: dict) -> dict | None:
    """upbit_collector.collect_btc_krw() 결과 + market.json(Phase 3 btc/usdkrw)으로 김치 프리미엄 산출."""
    if not upbit_data:
        return None
    as_of = datetime.now(timezone.utc).isoformat()
    change_abs = upbit_data["price"] - upbit_data["previous_close"] if upbit_data.get("previous_close") else None
    env = _envelope(as_of, upbit_data["price"], change_abs, upbit_data.get("change_pct"), "비트코인(KRW)")
    env["unit"], env["source"], env["session_key"] = "KRW", "upbit", "crypto_24h"

    btc_usd_q = market.get("btc")
    usdkrw_q = market.get("usdkrw")
    premium = kimchi_premium_pct(
        upbit_data["price"],
        btc_usd_q.price if btc_usd_q else None,
        usdkrw_q.price if usdkrw_q else None,
    )
    return {"envelope": env, "yoy": None, "next_release": None, "kimchi_premium_pct": premium}


def strip_as_of(market_strip: list[dict]) -> str:
    """스트립 전체의 기준시각 = 타일들 중 **가장 최신** as_of_iso.

    가장 오래된 값을 쓰면 심볼 하나의 결측이 카드 전체를 STALE로 끌어내린다. 라이브 표시는
    "이 카드가 마지막으로 새 값을 본 시각"을 말해야 하므로 최신값이 맞다(macro-live.js의
    asOf()와 같은 규칙 — 발행 시점과 폴링 이후의 판정이 어긋나면 안 된다).
    """
    stamps = [
        t["as_of_iso"]
        for g in market_strip
        for t in g.get("tiles", [])
        if t.get("as_of_iso")
    ]
    return max(stamps) if stamps else ""


def _aligned_dates(closes: list[float], dates: list[str] | None) -> list[str]:
    """종가와 길이가 일치하는 거래일만 같은 창으로 잘라 돌려준다. 불일치·결측이면 빈 리스트."""
    if not dates or len(dates) != len(closes):
        return []
    return spark.window(dates, max_points=STRIP_CHART_POINTS)


def build_market_strip(
    market: dict,
    history: dict[str, list[float]],
    history_dates: dict[str, list[str]] | None = None,
) -> list[dict]:
    """market.json Quote + 이력 → Macro "금융시장" 그룹 타일(design/25).

    확보되지 않은 키는 타일을 만들지 않는다(빈칸 렌더 금지). 이력이 없으면 `spark`가 빈
    문자열이 되어 미니차트만 빠지고 값·등락은 정상 표시된다 — 두 소스의 실패가 서로를
    무너뜨리지 않게 하는 것이 이 분리의 목적이다.
    그룹 전체가 결측이면 그룹 자체를 생략한다.
    """
    groups: list[dict] = []
    for group_name, keys in MACRO_STRIP_GROUPS:
        tiles: list[dict] = []
        for key in keys:
            quote = market.get(key)
            if not quote:
                continue
            closes = history.get(key) or []
            tiles.append({
                "key": key,
                "label": quote.name,
                "price": quote.price,
                "change_pct": quote.change_pct,
                "as_of": getattr(quote, "as_of", None),
                # 표시 문자열("08-05 18:21")과 별개로 ISO 원본을 함께 싣는다 — 라이브 표시
                # (펄스·"n분 전")는 **데이터 자신의 기준시각**으로만 판정해야 한다. 내려받은
                # 시각으로 판정하면 1시간 묵은 값도 방금 받았다는 이유로 라이브가 된다.
                "as_of_iso": getattr(quote, "as_of_iso", None),
                "unit": ENVELOPE_META.get(key, ("", "", 0, 1.0))[0],
                # 스파크라인은 진폭이 정규화돼 "얼마나" 움직였는지는 못 보여준다 —
                # 구간 등락률을 숫자로 병기해야 그림이 거짓말을 하지 않는다(design/25 §10).
                "period_change_pct": spark.period_change_pct(closes, max_points=STRIP_CHART_POINTS),
                # 화면이 그릴 실제 구간의 종가. 서버 SVG는 JS가 죽었을 때의 폴백이고, 축·
                # 고저 마커·호버 툴팁은 이 배열을 받은 chart.js가 그린다 — 좌표를 픽셀 실측으로
                # 잡아야 점이 타원으로 찌그러지지 않기 때문이다(static/js/chart.js 상단 주석).
                "closes": spark.window(closes, max_points=STRIP_CHART_POINTS),
                # 날짜는 종가와 길이가 **정확히 같을 때만** 싣는다 — 어긋난 축은 없는 축보다 나쁘다.
                "dates": _aligned_dates(closes, (history_dates or {}).get(key)),
                "spark": spark.sparkline_svg(
                    closes, width=200, height=48, label=f"{quote.name} 최근 추이",
                    css_class="v2-macro-spark", color_by_direction=True,
                    max_points=STRIP_CHART_POINTS, baseline=True,
                ),
            })
        if tiles:
            groups.append({"name": group_name, "tiles": tiles})
    return groups


def build_crypto_line(market: dict, btc_krw: dict | None) -> dict | None:
    """코인 한 줄 요약(design/25 — 카드 승격 금지, 단타 도구라 Macro의 주역이 아니다).

    원화 시세(Upbit)와 달러 시세(Yahoo) 중 확보된 것만 담고, 둘 다 있으면 김치 프리미엄까지
    한 줄에 붙인다. 아무것도 없으면 None → 템플릿이 줄 자체를 생략한다.
    """
    usd_quote = market.get(MACRO_CRYPTO_KEYS[0])
    if not btc_krw and not usd_quote:
        return None
    line: dict = {"label": "비트코인"}
    if btc_krw:
        env = btc_krw["envelope"]
        line["krw"] = env["value"]
        line["change_pct"] = env.get("change_pct")
        line["as_of_iso"] = env.get("as_of_iso")
        line["kimchi_premium_pct"] = btc_krw.get("kimchi_premium_pct")
    if usd_quote:
        line["usd"] = usd_quote.price
        line.setdefault("change_pct", usd_quote.change_pct)
    return line


def _event_at_utc(date_str: str, time_str: str | None, tz_name: str | None) -> str | None:
    """지역 날짜+시각+IANA 타임존 → UTC ISO. 서머타임(EDT/EST)은 zoneinfo가 날짜별로 정확히
    처리한다 — 템플릿에서 고정 오프셋 문자열을 하드코딩하면 DST 전환 시점에 틀린다."""
    if not time_str:
        return None
    try:
        hh, mm = (int(x) for x in time_str.split(":"))
        naive = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hh, minute=mm)
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
        return naive.replace(tzinfo=tz).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def build_calendar(fred_data: dict[str, dict | None]) -> dict:
    events: list[dict] = []
    for date_str, label in FOMC_2026:
        event = {
            "date": date_str, "time": FOMC_STATEMENT_TIME_ET, "timezone": "America/New_York",
            "label": label, "source": "fomc",
        }
        at_utc = _event_at_utc(date_str, FOMC_STATEMENT_TIME_ET, "America/New_York")
        if at_utc:
            event["event_at_utc"] = at_utc
        events.append(event)
    for series_id, label in FRED_SERIES:
        entry = fred_data.get(series_id)
        next_release = entry.get("next_release") if entry else None
        if next_release:
            events.append({
                "date": next_release, "time": None, "timezone": None,
                "label": f"{label} 발표", "source": "fred", "series_id": series_id,
            })
    events.sort(key=lambda e: e["date"])
    return {"as_of": datetime.now(timezone.utc).isoformat(), "events": events}


def persist(indicators: dict, calendar: dict, market_strip: list[dict] | None = None) -> dict:
    """발행 + last-good 보호(design/25 Phase A 파일럿 — macro 도메인 한정).

    반환값은 **병합된 지표**다 — 폴백으로 되살아난 항목이 화면에도 나가야 하므로 생성기가
    이 반환값을 렌더에 써야 한다(발행물과 화면이 어긋나면 안 된다).

    calendar는 병합 대상이 아니다 — 키-항목 매핑이 아니라 이벤트 목록이고, FOMC 수기 일정이
    항상 채워지므로 전량 결측이 구조적으로 불가능하다.
    """
    merged = domain_cache.save_keyed(DOCS_DIR / "data" / "macro" / "indicators.json", indicators)
    save_json(DOCS_DIR / "data" / "macro" / "calendar.json", calendar)
    if market_strip is not None:
        # 스파크라인 SVG는 표시 전용이라 데이터 파일에서는 제외한다(발행물 비대화 방지).
        save_json(
            DOCS_DIR / "data" / "macro" / "market_strip.json",
            [
                {"name": g["name"],
                 "tiles": [{k: v for k, v in t.items() if k != "spark"} for t in g["tiles"]]}
                for g in market_strip
            ],
        )
    return merged


def freshness_attrs() -> dict:
    return {"fresh_max_min": _FRESH_MAX_MIN, "stale_min_min": _STALE_MIN_MIN}
