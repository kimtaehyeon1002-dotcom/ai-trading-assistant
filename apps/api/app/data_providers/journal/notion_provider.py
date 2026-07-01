"""Notion 매매일지 프로바이더 — REST API로 '매매 일지 _ 쉽알남' DB 행을 정규화 거래로 매핑.

스키마(데이터소스 collection://fb9dbad2-41f8-832d-837f-873abc14def8):
  날짜(date) · 종목명(select BTC/ETH/SOL/XRP) · 포지션(select Long/Short) · 수익금(number USD)
  · 승/무/패(checkbox) · 매매 복기(title 텍스트)

NOTION_API_KEY/NOTION_JOURNAL_DATABASE_ID 없으면 결정적 스텁 픽스처 반환(오프라인 검증/데모).
구조화 필드만 매핑하므로 자유텍스트 프롬프트 인젝션 위험 없음(복기 note는 사용자 본인 기록).
"""
from __future__ import annotations

from datetime import date

from app.analytics.journal_metrics import derive_outcome
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.journal import JournalTrade

log = get_logger("notion_journal")

_POS_MAP = {"Long": "long", "Short": "short"}


def _title_text(prop: dict | None) -> str | None:
    if not prop:
        return None
    parts = prop.get("title") or []
    text = "".join(p.get("plain_text", "") for p in parts).strip()
    return text or None


def _map_row(row: dict) -> JournalTrade | None:
    props = row.get("properties") or {}

    def sel(name: str) -> str | None:
        s = (props.get(name) or {}).get("select")
        return s.get("name") if s else None

    def chk(name: str) -> bool:
        return bool((props.get(name) or {}).get("checkbox"))

    def num(name: str):
        return (props.get(name) or {}).get("number")

    def dstart(name: str) -> str | None:
        d = (props.get(name) or {}).get("date")
        return d.get("start") if d else None

    pnl = num("수익금")
    win, draw, loss = chk("승"), chk("무"), chk("패")
    traded = None
    ds = dstart("날짜")
    if ds:
        try:
            traded = date.fromisoformat(ds[:10])
        except ValueError:
            traded = None
    posname = sel("포지션")
    return JournalTrade(
        row_id=row.get("id") or "",
        traded_on=traded,
        symbol=sel("종목명"),
        position=_POS_MAP.get(posname) if posname else None,
        pnl=pnl,
        outcome=derive_outcome(win=win, draw=draw, loss=loss, pnl=pnl),
        note=_title_text(props.get("매매 복기")),
    )


class NotionJournalProvider:
    def __init__(self) -> None:
        self._key = settings.notion_api_key
        self._db = settings.notion_journal_database_id

    @property
    def enabled(self) -> bool:
        return bool(self._key and self._db)

    async def fetch_trades(self) -> list[JournalTrade]:
        if not self.enabled:
            return _stub_trades()
        import httpx

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Notion-Version": settings.notion_version,
            "Content-Type": "application/json",
        }
        url = f"{settings.notion_base_url}/databases/{self._db}/query"
        out: list[JournalTrade] = []
        cursor: str | None = None
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                body: dict = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                for row in data.get("results", []):
                    t = _map_row(row)
                    if t and t.row_id:
                        out.append(t)
                if data.get("has_more"):
                    cursor = data.get("next_cursor")
                else:
                    break
        return out


def _stub_trades() -> list[JournalTrade]:
    """오프라인/토큰 미설정용 결정적 픽스처(실제 스키마 형태)."""
    raw = [
        ("stub-1", "2026-06-01", "BTC", "long", 120.0, "win", "추세 따라 진입, 분할 청산"),
        ("stub-2", "2026-06-02", "BTC", "long", -60.0, "loss", "되돌림에서 손실 관리 실패"),
        ("stub-3", "2026-06-03", "ETH", "short", 200.0, "win", "저항 거부 확인 후 대응"),
        ("stub-4", "2026-06-04", "ETH", "short", -40.0, "loss", "변동성 과대평가"),
        ("stub-5", "2026-06-05", "SOL", "long", -25.0, "loss", "연속 대응 중 과잉 거래"),
        ("stub-6", "2026-06-08", "BTC", "long", 0.0, "draw", "본전 청산"),
        ("stub-7", "2026-06-09", "XRP", "long", 35.0, "win", "소액 테스트"),
    ]
    return [
        JournalTrade(
            row_id=rid,
            traded_on=date.fromisoformat(d),
            symbol=sym,
            position=pos,
            pnl=pnl,
            outcome=oc,
            note=note,
        )
        for rid, d, sym, pos, pnl, oc, note in raw
    ]


_provider: NotionJournalProvider | None = None


def get_notion_journal_provider() -> NotionJournalProvider:
    global _provider
    if _provider is None:
        _provider = NotionJournalProvider()
    return _provider
