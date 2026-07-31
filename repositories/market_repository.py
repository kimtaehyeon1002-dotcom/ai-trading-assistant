"""검증된 시장 raw → Quote 모델 + cache/market.json 기록(Envelope 규격, schema/envelope.schema.json)."""
from __future__ import annotations

from datetime import datetime, timezone

from collectors.kiwoom_collector import LABELS as NIGHT_LABELS
from config.markets import (
    BASE_PREV_CLOSE,
    ENVELOPE_META,
    EXTENDED_SYMBOLS,
    MORNING_US_INDICES,
    NIGHT_BASIS_NOTE,
)
from config.settings import CACHE_DIR
from models.market import Quote
from utils.dates import fmt_kst, now_kst
from utils.jsonio import save_json


def _as_of_kst(iso: str) -> str:
    """ISO 타임스탬프 → 'MM-DD HH:MM' KST 표시 문자열(파싱 실패 시 빈 문자열)."""
    try:
        return fmt_kst(datetime.fromisoformat(iso), "%m-%d %H:%M")
    except (ValueError, TypeError):
        return ""

_NAMES = {
    **NIGHT_LABELS,
    "usdkrw": "USD/KRW 환율",
    "wti": "WTI 국제유가",
    **{key: label for key, _sym, label in MORNING_US_INDICES},
    **{key: label for key, _sym, label in EXTENDED_SYMBOLS},
}
_CURRENCY = {
    "usdkrw": "KRW", "kospi_night": "KRW", "kosdaq_night": "KRW",
    "kospi": "KRW", "kosdaq": "KRW",
    "usdjpy": "JPY", "eurusd": "USD", "usdcny": "CNY",
}
_DEFAULT_META = ("", "none", 60, 1.0)  # (unit, session_key, expected_T_min, scale) — 유니버스 미등재 심볼용


def to_quotes(validated: dict[str, dict | None]) -> dict[str, Quote | None]:
    """raw price에 심볼별 scale(예: ^TNX 수익률×10 → ×0.1)을 적용해 Quote를 만든다.

    change_pct는 (price/prev-1)*100 비율이라 scale에 불변(수집 단계에서 이미 정확) — 재계산하지 않는다.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    out: dict[str, Quote | None] = {}
    for key, e in validated.items():
        if e is None:
            out[key] = None
            continue
        _unit, session_key, _t, scale = ENVELOPE_META.get(key, _DEFAULT_META)
        price = e["price"] * scale
        prev = e.get("previous_close")
        prev_scaled = (prev * scale) if isinstance(prev, (int, float)) else None
        change_abs = (price - prev_scaled) if prev_scaled is not None else None
        # 표시용 as_of와 판정용 as_of_iso는 반드시 같은 시각이어야 한다. 종전에는 표시용만
        # e["as_of"]에서 뽑아, 그 필드가 없는 라이브 수집분(Yahoo)은 화면에 기준 시각이
        # 아예 비었다 — 값의 나이를 눈으로 확인할 수단이 없었다(design/23 P5).
        as_of_iso = e.get("as_of") or now_iso
        out[key] = Quote(
            symbol=key,
            name=_NAMES.get(key, key),
            price=price,
            change_pct=e.get("change_pct"),
            currency=_CURRENCY.get(key, "USD"),
            source=e.get("source", ""),
            as_of=_as_of_kst(as_of_iso),
            as_of_iso=as_of_iso,
            change_abs=change_abs,
            session_key=session_key,
            quality=e.get("quality", "unverified"),
            # 야간선물만 실어 보내는 등락 기준 메타(design/27). 가격과 달리 기준가는 이미
            # 표시 단위이므로 scale을 곱하지 않는다 — 야간선물 scale은 1.0이고, 배율이 붙는
            # 심볼(^TNX)은 애초에 이 필드를 채우지 않는다.
            ref_price=e.get("ref_price"),
            base_kind=e.get("base_kind"),
        )
    return out


def to_envelope_dict(quotes: dict[str, Quote | None]) -> dict:
    """Quote 맵 → market.json 본문(컨테이너 스키마 대상). 최상위 as_of는 호출부(persist)가 덧붙인다."""
    body: dict[str, dict | None] = {}
    for key, q in quotes.items():
        if q is None:
            body[key] = None
            continue
        unit, _session, expected_t, _scale = ENVELOPE_META.get(key, _DEFAULT_META)
        env = {
            "value": q.price,
            "change_abs": q.change_abs,
            "change_pct": q.change_pct,
            "unit": unit,
            "as_of_iso": q.as_of_iso,
            "source": q.source,
            "session_key": q.session_key,
            "expected_T_min": expected_t,
            "freshness_basis": "as_of",
            "label": q.name,
            "quality": q.quality,
        }
        if q.ref_price is not None:
            env["ref_price"] = q.ref_price
        if q.base_kind:
            env["base_kind"] = q.base_kind
        body[key] = env
    return body


def night_basis_note(quotes: dict[str, Quote | None]) -> str | None:
    """야간선물 등락 기준 고지 문구 — 야간선물이 하나도 없으면 None.

    두 종목의 기준이 갈리면(한쪽만 종가 확보) **약한 쪽**을 고지한다. 화면에는 두 타일이
    나란히 놓이는데 "밤사이 변동분"이라고 단언해버리면 나머지 하나를 잘못 읽게 된다.
    """
    kinds = [q.base_kind for k, q in quotes.items() if k in NIGHT_LABELS and q]
    if not kinds:
        return None
    kind = BASE_PREV_CLOSE if any(k != kinds[0] for k in kinds) else (kinds[0] or BASE_PREV_CLOSE)
    return NIGHT_BASIS_NOTE.get(kind, NIGHT_BASIS_NOTE[BASE_PREV_CLOSE])


def persist(quotes: dict[str, Quote | None]) -> None:
    save_json(
        CACHE_DIR / "market.json",
        {"as_of": now_kst().isoformat(), **to_envelope_dict(quotes)},
    )
