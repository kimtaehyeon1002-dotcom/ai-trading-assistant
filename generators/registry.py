"""타깃 → 생성기 레지스트리 (design/22 §6). build.py가 이걸 순회 디스패치한다(if 분기 제거).

`in_all=True`인 타깃만 "all" 실행 시 포함된다("all"의 정기 발행 그룹). 대시보드·정적 자산·
AI Office 공통 마무리는 build.py가 레지스트리와 무관하게 항상 수행한다(변경 없음).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Target:
    name: str
    generate: Callable[[], Path | None]
    in_all: bool = False  # "all" 실행 시 포함 여부


def _morning() -> Path | None:
    from utils.logging import get_logger

    from generators.morning.generate import generate

    out = generate()
    # TA는 저비용·저빈도(1일1회) 데이터라 별도 워크플로 없이 morning 타깃에 편입한다
    # (design/21 §5-2 "ta는 morning.yml에 편입"). 이 페이지는 라이브 무간섭 원칙(design/20 Phase 2
    # 리스크·롤백)의 대상이라, 신규 기능 오류가 기존 모닝리포트 발행을 막지 않도록 예외를 흡수한다.
    try:
        from generators.ta.generate import generate as gen_ta
        gen_ta()
    except Exception as exc:  # noqa: BLE001
        get_logger("gen.registry").warning("TA 페이지 생성 실패(모닝리포트는 계속 발행): %s", exc)
    return out


def _news() -> Path:
    # design/20 Phase 5: News가 v2로 치환됐다. v1 생성기(generators/news)·템플릿(news.html)은
    # Phase 9 v1 셸 은퇴로 소스에서 제거됐다 — 필요 시 git 히스토리에서 복원한다.
    from generators.news_v2.generate import generate
    return generate()


def _trades() -> Path:
    # design/20 Phase 8: 매매일지가 v2로 치환됐다("공개 v2 치환", 게이트 없음). v1 생성기
    # (generators/trades)·템플릿(trades.html)은 Phase 9 v1 셸 은퇴로 소스에서 제거됐다 —
    # 필요 시 git 히스토리에서 복원한다.
    from generators.trades_v2.generate import generate
    return generate()


def _v2preview() -> Path:
    from generators.skeleton_v2 import generate
    return generate()


def _macro() -> Path:
    from generators.macro.generate import generate
    return generate()


def _stock() -> Path:
    from generators.stock.generate import generate
    return generate()


def _financials() -> Path:
    from generators.financials.generate import generate
    return generate()


def _asset() -> Path:
    from generators.asset.generate import generate
    return generate()


def _portfolio() -> Path:
    from generators.portfolio.generate import generate
    return generate()


def _settings() -> Path:
    from generators.settings.generate import generate
    return generate()


TARGETS: dict[str, Target] = {
    "morning": Target("morning", _morning, in_all=True),
    "news": Target("news", _news, in_all=True),
    "trades": Target("trades", _trades, in_all=True),
    # v2preview는 nav 미노출 스켈레톤 라우트 확인용(design/20 Phase 1) — "all"에는 포함하지 않는다.
    "v2preview": Target("v2preview", _v2preview, in_all=False),
    # macro는 시세 유니버스에 의존하지 않는 독립 트랙(design/20 Phase 6) — 자체 60분 cron
    # (macro.yml)을 가지므로 기존 30분/06:30 그룹인 "all"에는 포함하지 않는다.
    "macro": Target("macro", _macro, in_all=False),
    # stock은 KR/US 랭킹 배치(design/20 Phase 7) — 자체 cron(stock.yml, KR 장중+마감·US 마감후)을
    # 가지므로 기존 30분/06:30 그룹인 "all"에는 포함하지 않는다(macro와 동일 원칙).
    "stock": Target("stock", _stock, in_all=False),
    # financials는 분기 공시 주기 데이터(design/06 §1-5)라 일1회면 충분 — 자체 cron(financials.yml).
    # "stock" 타깃이 먼저 발행한 universe.json·Hub 종가를 재사용하므로 stock 이후 실행돼야 한다.
    "financials": Target("financials", _financials, in_all=False),
    # asset은 Kiwoom(데스크톱 OCX 전용) + KIS/BYBIT(REST) 4계좌 자동 수집(design/20 Phase 8) —
    # 일1회, ASSET_PASSPHRASE 미설정 시 암호화 발행만 skip하고 게이트 셸은 항상 렌더한다.
    "asset": Target("asset", _asset, in_all=False),
    # portfolio는 자체 수집 없이 asset이 발행한 assets.enc.json을 재사용한다(design/08 §1 게이트
    # 세션 공유) — asset 타깃 실행 이후 배치돼야 최신 암호문을 읽지만, 셸 자체는 독립적으로 렌더된다.
    "portfolio": Target("portfolio", _portfolio, in_all=False),
    # settings는 서버 데이터가 없는 순수 클라이언트 페이지(design/20 Phase 9) — 비용이 거의
    # 없어 "all"에 포함해 항상 최신 템플릿 상태로 유지한다.
    "settings": Target("settings", _settings, in_all=True),
}

ALL_TARGETS: tuple[str, ...] = tuple(name for name, t in TARGETS.items() if t.in_all)
