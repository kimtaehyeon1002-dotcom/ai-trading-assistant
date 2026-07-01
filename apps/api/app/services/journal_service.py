"""매매일지 서비스 — Notion 임포트(멱등) + 조회 + 코드 메트릭. 설계서 §1.3-C, §2.4.

정량 메트릭은 LLM 비의존(analytics.journal_metrics). 임포트는 source_row_id로 중복 제거.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.journal_metrics import TradeInput, compute_metrics
from app.core.logging import get_logger
from app.data_providers.journal.notion_provider import get_notion_journal_provider
from app.models.journal import TradeJournalEntry
from app.schemas.journal import ImportResult

log = get_logger("journal")


async def import_from_notion(session: AsyncSession, user_id: uuid.UUID) -> ImportResult:
    provider = get_notion_journal_provider()
    trades = await provider.fetch_trades()

    existing = set(
        (
            await session.execute(
                select(TradeJournalEntry.source_row_id).where(
                    TradeJournalEntry.user_id == user_id, TradeJournalEntry.source == "notion"
                )
            )
        )
        .scalars()
        .all()
    )

    imported = 0
    for t in trades:
        if t.row_id in existing:
            continue
        session.add(
            TradeJournalEntry(
                user_id=user_id,
                source="notion",
                source_row_id=t.row_id,
                symbol=t.symbol,
                position=t.position,
                pnl=Decimal(str(t.pnl)) if t.pnl is not None else None,
                outcome=t.outcome,
                traded_on=t.traded_on,
                note=t.note,
            )
        )
        imported += 1
    await session.commit()
    log.info("journal_import", user_id=str(user_id), imported=imported, total=len(trades))
    return ImportResult(
        source="notion",
        imported=imported,
        skipped=len(trades) - imported,
        total_seen=len(trades),
        is_stub=not provider.enabled,
    )


async def get_entries(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 200
) -> list[TradeJournalEntry]:
    rows = (
        await session.execute(
            select(TradeJournalEntry)
            .where(TradeJournalEntry.user_id == user_id)
            .order_by(TradeJournalEntry.traded_on.desc().nullslast())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


def _to_inputs(entries: list[TradeJournalEntry]) -> list[TradeInput]:
    return [
        TradeInput(
            traded_on=e.traded_on,
            symbol=e.symbol,
            position=e.position,
            pnl=float(e.pnl) if e.pnl is not None else None,
            outcome=e.outcome,
        )
        for e in entries
    ]


async def compute_user_metrics(session: AsyncSession, user_id: uuid.UUID) -> dict:
    entries = await get_entries(session, user_id, limit=10000)
    return compute_metrics(_to_inputs(entries))
