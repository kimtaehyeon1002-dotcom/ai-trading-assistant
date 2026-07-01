"""Claude 툴 정의 + 실행기. 설계서 §2.3 공용 툴 카탈로그.

Phase 2 리서치는 '결정적 코드 오케스트레이션'으로 gather_context()가 직접 수집하고,
각 수집을 SSE 'tool' 이벤트로 노출한다(비용/지연 통제·재현성). TOOLS 스키마는 향후
LLM 주도 tool-use 루프 확장을 위한 자리다(설계서 §2.1).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.config import settings
from app.data_providers.errors import ProviderError
from app.models.instrument import Instrument
from app.services import market_service

PushFn = Callable[[str, object], Awaitable[None]]

# 향후 LLM tool-use 루프용 스키마(현재는 코드가 직접 호출)
TOOLS: list[dict] = [
    {
        "name": "get_quote",
        "description": "정규화된 현재가/등락/거래량 조회(출처·신선도 메타 포함)",
        "input_schema": {
            "type": "object",
            "properties": {"instrument_id": {"type": "integer"}},
            "required": ["instrument_id"],
        },
    },
    {
        "name": "get_candles",
        "description": "OHLCV 시계열 조회(추세 관찰용)",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {"type": "integer"},
                "interval": {"type": "string", "enum": ["1m", "5m", "1h", "1d"]},
            },
            "required": ["instrument_id"],
        },
    },
    {
        "name": "search_news",
        "description": "헤드라인+자체요약+URL 조회(본문 미저장, 저작권 안전)",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "rag_search",
        "description": "RAG(뉴스·공시 벡터 인덱스)에서 관련 청크+인용 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_theme_scores",
        "description": "테마 강도 스코어(코드 계산 관찰 지표) 조회 — score·rank·구성요소. 매수 신호 아님",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KR", "US"]},
                "timeframe": {"type": "string", "enum": ["intraday", "swing", "long"]},
                "top_k": {"type": "integer"},
            },
            "required": ["market"],
        },
    },
]


async def gather_context(
    session, inst: Instrument, push: PushFn, *, query: str | None = None, user_id=None
) -> dict:
    """시세 → 캔들 추세 요약 → 뉴스 → RAG 검색 순으로 수집. 개별 실패는 건너뜀(부분 성공).

    인용 번호(citations[].n)는 뉴스 → RAG 순으로 단조 증가하도록 공유한다.
    """
    from app.schemas.research import Citation  # 지연 임포트(순환 회피)

    ctx: dict = {}
    citations: list[Citation] = []

    # 1) 시세
    try:
        q = await market_service.get_quote(session, inst)
        ctx["quote"] = {
            "price": q.price,
            "currency": q.currency,
            "change_pct": q.change_pct,
            "volume": q.volume,
            "source": q.meta.source,
            "as_of": q.meta.as_of.isoformat(),
            "is_realtime": q.meta.is_realtime,
        }
        await push(
            "tool",
            {
                "tool": "get_quote",
                "ok": True,
                "summary": f"{q.price} {q.currency} ({q.change_pct}%)",
                "source": q.meta.source,
            },
        )
    except ProviderError:
        await push("tool", {"tool": "get_quote", "ok": False, "error": "시세 미수집"})

    # 2) 캔들 추세 요약(최근 일봉)
    try:
        series = await market_service.get_candles(session, inst, "1d", None, None)
        cs = series.candles[-20:]
        if cs:
            first, last = cs[0].close, cs[-1].close
            pct = round((last - first) / first * 100, 2) if first else None
            ctx["trend"] = f"최근 {len(cs)}봉 종가 {first}→{last} (구간 {pct}%)"
            await push(
                "tool",
                {"tool": "get_candles", "ok": True, "summary": ctx["trend"], "source": series.meta.source},
            )
    except ProviderError:
        await push("tool", {"tool": "get_candles", "ok": False, "error": "캔들 미수집"})

    # 3) 뉴스 헤드라인(본문 미저장)
    try:
        news = await market_service.get_news(inst.market, [inst.symbol_norm, inst.ticker], None, 5)
        items = []
        for i, n in enumerate(news[:5], 1):
            items.append(
                {
                    "title": n.title,
                    "source": n.source_name,
                    "published_at": n.published_at.isoformat(),
                    "url": n.url,
                }
            )
            citations.append(
                Citation(n=i, title=n.title, url=n.url, source=n.source_name, published_at=n.published_at)
            )
        ctx["news"] = items
        await push("tool", {"tool": "search_news", "ok": True, "count": len(items)})
    except ProviderError:
        await push("tool", {"tool": "search_news", "ok": False, "error": "뉴스 미수집"})

    # 4) RAG 검색(뉴스·공시 벡터 인덱스) — 인용 번호는 뉴스 다음부터 이어붙임
    try:
        from app.services import rag_service

        rag_query = query or (inst.name_local or inst.name_en or inst.symbol_norm)
        hits = await rag_service.search(
            session,
            rag_query,
            user_id=user_id,
            symbols=[inst.symbol_norm, inst.ticker],
            market=inst.market,
            doc_types=["news"],
            k=settings.rag_top_k,
        )
        rag_ctx = []
        for h in hits:
            n = len(citations) + 1
            rag_ctx.append({"n": n, "title": h["title"] or "(제목 없음)", "snippet": h["snippet"]})
            citations.append(
                Citation(
                    n=n,
                    title=h["title"] or "(제목 없음)",
                    url=h["url"],
                    source=h["source"],
                    published_at=h["published_at"],
                )
            )
        if rag_ctx:
            ctx["rag"] = rag_ctx
        await push("tool", {"tool": "rag_search", "ok": True, "count": len(rag_ctx)})
    except Exception:  # noqa: BLE001 - RAG 보강 실패는 리서치를 막지 않음
        await push("tool", {"tool": "rag_search", "ok": False, "error": "RAG 검색 불가"})

    return {"ctx": ctx, "citations": citations}
