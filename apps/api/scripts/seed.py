"""초기 시드 — data_provider_source + 샘플 instrument + 오너 계정. 멱등.

실행: docker compose exec api python -m scripts.seed
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.data_provider_source import DataProviderSource
from app.models.instrument import Instrument
from app.models.theme import Theme, ThemeMembership
from app.services.auth_service import create_local_user, get_user_by_email

_PROVIDERS = [
    dict(name="fdr", tier="free", domain="price", markets=["KR"], is_realtime=False, priority=40,
         terms_note="비공식 스크래핑 — 내부/PoC 한정"),
    dict(name="pykrx", tier="free", domain="price", markets=["KR"], is_realtime=False, priority=45,
         terms_note="KRX 비공식 — 과호출 주의"),
    dict(name="yfinance", tier="free", domain="price", markets=["US", "KR"], is_realtime=False,
         priority=50, terms_note="Yahoo ToS 위반 소지 — 상업 재배포 금지"),
    dict(name="rss", tier="free", domain="news", markets=["KR", "US"], is_realtime=True, priority=50,
         terms_note="헤드라인+링크만, 본문 미저장(저작권)"),
    dict(name="yfinance_fx", tier="free", domain="fx", markets=["KR", "US"], is_realtime=False,
         priority=60, terms_note="향후 KIS/ECOS/ECB로 보강"),
]

_INSTRUMENTS = [
    dict(market="KR", ticker="005930", symbol_norm="005930.KS", exchange="KRX",
         name_local="삼성전자", name_en="Samsung Electronics", currency="KRW",
         timezone="Asia/Seoul", sector="IT"),
    dict(market="US", ticker="AAPL", symbol_norm="AAPL", exchange="NASDAQ",
         name_local="애플", name_en="Apple Inc.", currency="USD",
         timezone="America/New_York", sector="Technology"),
]


async def seed() -> None:
    async with SessionLocal() as session:
        # providers
        for p in _PROVIDERS:
            exists = await session.execute(
                select(DataProviderSource).where(
                    DataProviderSource.name == p["name"],
                    DataProviderSource.domain == p["domain"],
                )
            )
            if exists.scalar_one_or_none() is None:
                session.add(DataProviderSource(**p))
        # instruments
        for i in _INSTRUMENTS:
            exists = await session.execute(
                select(Instrument).where(Instrument.symbol_norm == i["symbol_norm"])
            )
            if exists.scalar_one_or_none() is None:
                session.add(Instrument(**i))
        await session.commit()

        # themes + memberships (테마 스코어 데모용)
        inst_by_symbol = {
            i.symbol_norm: i
            for i in (await session.execute(select(Instrument))).scalars().all()
        }
        _THEMES = [
            dict(market="US", slug="us-bigtech", name="미국 빅테크", tags=["tech"],
                 kr_link_slug="kr-semiconductor", members=["AAPL"]),
            dict(market="KR", slug="kr-semiconductor", name="한국 반도체", tags=["semiconductor"],
                 kr_link_slug=None, members=["005930.KS"]),
        ]
        for t in _THEMES:
            existing = await session.execute(select(Theme).where(Theme.slug == t["slug"]))
            theme = existing.scalar_one_or_none()
            if theme is None:
                theme = Theme(
                    market=t["market"], slug=t["slug"], name=t["name"],
                    tags=t["tags"], kr_link_slug=t["kr_link_slug"],
                )
                session.add(theme)
                await session.flush()
            for sym in t["members"]:
                inst = inst_by_symbol.get(sym)
                if inst is None:
                    continue
                dup = await session.execute(
                    select(ThemeMembership).where(
                        ThemeMembership.theme_id == theme.theme_id,
                        ThemeMembership.instrument_id == inst.instrument_id,
                    )
                )
                if dup.scalar_one_or_none() is None:
                    session.add(
                        ThemeMembership(theme_id=theme.theme_id, instrument_id=inst.instrument_id)
                    )
        await session.commit()

        # owner 계정
        if await get_user_by_email(session, "owner@thbot.local") is None:
            await create_local_user(
                session,
                email="owner@thbot.local",
                password="changeme123",
                display_name="Owner",
                role="OWNER",
                investment_styles=["scalping", "swing", "long"],
            )
        owner = await get_user_by_email(session, "owner@thbot.local")
        if owner is not None and owner.plan != "enterprise":
            owner.plan = "enterprise"  # 단일 오너는 쿼터 제한 없이
            await session.commit()
    print("seed: done (owner@thbot.local / changeme123)")


if __name__ == "__main__":
    asyncio.run(seed())
