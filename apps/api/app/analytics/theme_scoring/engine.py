"""Theme Scoring 오케스트레이션 — 구성종목 시세 수집 → 신호 집계 → 정규화 → theme_score 적재.

설계서 §2.7. EOD/장전 06:00 잡 + 모닝리포트가 호출. 시세는 Provider(get_candles)로 수집하며
종목당 N콜이라 캐시 권장. 결측(데이터 부족)은 중립 신호로 흡수한다.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.theme_scoring.scoring import ThemeScoreResult, composite_scores
from app.analytics.theme_scoring.signals import Constituent, ThemeRaw, theme_raw_signals
from app.core.logging import get_logger
from app.data_providers.errors import ProviderError
from app.data_providers.normalization import now_utc
from app.models.instrument import Instrument
from app.models.theme import Theme, ThemeMembership, ThemeScore
from app.services import market_service

log = get_logger("theme_scoring")

# timeframe → 스타일 가중 프리셋
_TIMEFRAME_STYLE = {"intraday": "scalping", "swing": "swing", "long": "long"}


def _returns_and_volume(candles) -> tuple[dict[str, float], float | None, float | None]:
    closes = [c.close for c in candles if c.close]
    vols = [c.volume for c in candles if c.volume is not None]
    ret: dict[str, float] = {}
    for label, n in (("1d", 1), ("5d", 5), ("20d", 20)):
        if len(closes) > n and closes[-1 - n]:
            ret[label] = (closes[-1] - closes[-1 - n]) / closes[-1 - n] * 100.0
    vol = vols[-1] if vols else None
    avg_vol = (sum(vols[-20:]) / len(vols[-20:])) if vols else None
    return ret, vol, avg_vol


async def _load_themes(
    session: AsyncSession, market: str
) -> tuple[dict[str, list[tuple[Instrument, float]]], dict[str, Theme]]:
    """(slug → [(instrument, weight)], slug → Theme) 활성 테마 구성종목 로드."""
    themes = (
        (await session.execute(select(Theme).where(Theme.market == market, Theme.is_active.is_(True))))
        .scalars()
        .all()
    )
    out: dict[str, list[tuple[Instrument, float]]] = {}
    for th in themes:
        rows = (
            await session.execute(
                select(ThemeMembership, Instrument)
                .join(Instrument, ThemeMembership.instrument_id == Instrument.instrument_id)
                .where(ThemeMembership.theme_id == th.theme_id)
            )
        ).all()
        out[th.slug] = [(inst, float(m.weight)) for m, inst in rows]
    return out, {t.slug: t for t in themes}


async def compute_theme_scores(
    session: AsyncSession,
    *,
    market: str,
    timeframe: str = "swing",
    as_of: datetime | None = None,
    persist: bool = True,
) -> list[ThemeScoreResult]:
    """시장 내 테마들의 4신호를 수집·정규화해 ThemeScoreResult 리스트 반환(+선택 적재)."""
    members, theme_by_slug = await _load_themes(session, market)
    if not members:
        return []

    # 1) 구성종목 메트릭 수집(시세) — 종목 단위 1회만(중복 종목 캐시)
    metric_cache: dict[int, tuple[dict[str, float], float | None, float | None]] = {}

    async def metrics_for(inst: Instrument):
        if inst.instrument_id in metric_cache:
            return metric_cache[inst.instrument_id]
        try:
            series = await market_service.get_candles(session, inst, "1d", None, None)
            m = _returns_and_volume(series.candles)
        except ProviderError:
            m = ({}, None, None)
        metric_cache[inst.instrument_id] = m
        return m

    # 2) 벤치마크(시장 프록시) = 전체 구성종목 호라이즌별 평균 수익률
    bench_acc: dict[str, list[float]] = {"1d": [], "5d": [], "20d": []}
    theme_constituents: dict[str, list[Constituent]] = {}
    for slug, items in members.items():
        cons: list[Constituent] = []
        for inst, weight in items:
            ret, vol, avg_vol = await metrics_for(inst)
            for h in ("1d", "5d", "20d"):
                if h in ret:
                    bench_acc[h].append(ret[h])
            cons.append(
                Constituent(
                    instrument_id=inst.instrument_id,
                    mcap=weight,
                    ret=ret,
                    vol=vol,
                    avg_vol=avg_vol,
                    news_recent=0,  # MVP: 뉴스 가속도는 중립(향후 rag_chunk 윈도 카운트)
                    news_baseline=0.0,
                )
            )
        theme_constituents[slug] = cons
    benchmark = {h: (sum(v) / len(v) if v else 0.0) for h, v in bench_acc.items()}

    # 3) 신호 집계 → 횡단면 정규화·가중·랭크
    raws: dict[str, ThemeRaw] = {
        slug: theme_raw_signals(cons, benchmark_ret=benchmark, timeframe=timeframe)
        for slug, cons in theme_constituents.items()
    }
    style = _TIMEFRAME_STYLE.get(timeframe, "swing")
    results = composite_scores(raws, style=style)

    # 4) 적재(시계열)
    if persist:
        stamp = as_of or now_utc()
        for r in results:
            theme = theme_by_slug.get(r.key)
            if theme is None:
                continue
            session.add(
                ThemeScore(
                    theme_id=theme.theme_id,
                    market=market,
                    as_of=stamp,
                    timeframe=timeframe,
                    score=r.score,
                    components={"z": r.components, "raw": r.raw, "missing": r.missing},
                    rank=r.rank,
                    percentile=r.percentile,
                    weights_version=r.weights_version,
                )
            )
        await session.commit()
        log.info("theme_scores_persisted", market=market, timeframe=timeframe, n=len(results))
    return results


async def get_latest_scores(
    session: AsyncSession, *, market: str, timeframe: str = "swing", top_k: int = 10
) -> list[dict]:
    """가장 최근 배치(max as_of)의 테마 스코어를 rank 순으로 반환(get_theme_scores 툴용)."""
    latest = (
        await session.execute(
            select(ThemeScore.as_of)
            .where(ThemeScore.market == market, ThemeScore.timeframe == timeframe)
            .order_by(ThemeScore.as_of.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return []
    rows = (
        await session.execute(
            select(ThemeScore, Theme)
            .join(Theme, ThemeScore.theme_id == Theme.theme_id)
            .where(
                ThemeScore.market == market,
                ThemeScore.timeframe == timeframe,
                ThemeScore.as_of == latest,
            )
            .order_by(ThemeScore.rank)
            .limit(top_k)
        )
    ).all()
    return [
        {
            "theme": th.name,
            "slug": th.slug,
            "score": float(ts.score),
            "rank": ts.rank,
            "percentile": float(ts.percentile),
            "components": ts.components,
            "as_of": ts.as_of.isoformat(),
            "weights_version": ts.weights_version,
        }
        for ts, th in rows
    ]
