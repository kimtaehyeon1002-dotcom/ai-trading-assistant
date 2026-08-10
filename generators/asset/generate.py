"""Asset 생성 — 4계좌 자동 수집 + 암호화 발행 + 게이트 셸 렌더(design/08, design/20 Phase 8).

Kiwoom은 32-bit OCX(Windows 데스크톱 세션) 없이는 조회 불가하므로, 이 함수는 app/sync.py(데스크톱)
에서 실행될 때만 Kiwoom 잔고를 포함한다 — CI(GitHub Actions, ubuntu-latest)에서 실행되면
KiwoomAPI() 생성이 KiwoomError로 실패해 Kiwoom 계좌만 결측 처리되고 나머지(KIS·BYBIT)는
정상 수집된다(부분 실패 허용, design/21 원칙과 동일). 페이지 자체(asset.html)에는 실제 숫자를
전혀 렌더하지 않는다 — 전 수치는 암호문 payload 안에서만 존재한다(design/20 Phase 8 DoD 1).
"""
from __future__ import annotations

from pathlib import Path

from config import nav
from config.settings import DOCS_DIR
from generators import pipelines
from generators.base import render
from repositories import asset_repository, asset_snapshot_repository
from utils import runlog
from utils.dates import fmt_kst, now_kst
from utils.logging import get_logger

log = get_logger("gen.asset")


def generate() -> Path:
    # design/25 Phase B: 4계좌 수집은 파이프라인 몫이다(생성기는 외부 소스를 직접 부르지 않는다).
    raw = pipelines.get_asset_raw()
    kiwoom_raw = raw["kiwoom"]
    kis_foreign_raw = raw["kis_foreign"]
    kis_isa_raw = raw["kis_isa"]
    bybit_raw = raw["bybit"]

    market = pipelines.get_market()
    usdkrw_q = market.get("usdkrw")
    usdkrw = usdkrw_q.price if usdkrw_q else None

    prev = asset_snapshot_repository.previous_snapshot()
    prev_accounts = (prev or {}).get("accounts", {})

    accounts = [
        asset_repository.build_kiwoom_account(kiwoom_raw, prev_accounts.get("kiwoom")),
        asset_repository.build_kis_isa_account(kis_isa_raw, prev_accounts.get("kis_isa")),
        asset_repository.build_kis_foreign_account(kis_foreign_raw, usdkrw, prev_accounts.get("kis_foreign")),
        asset_repository.build_bybit_account(bybit_raw, usdkrw, prev_accounts.get("bybit")),
    ]

    # 수집 주체가 둘로 갈렸다(design/28) — CI는 KIS·BYBIT만, 데스크톱은 Kiwoom도. 자기가 못 본
    # 계좌를 결측으로 발행하면 상대가 넣은 값이 매번 사라지므로, 직전 발행물에서 승계한다.
    accounts, carried = asset_repository.carry_forward(
        accounts, asset_repository.load_published_accounts())

    payload = asset_repository.build_payload(accounts, carried=carried)
    covered, missing = payload["covered_roles"], payload["missing_roles"]
    published = asset_repository.persist_encrypted(payload)

    if published:
        # **이번 실행에서 실제로 수집한** 4계좌 전량일 때만 원장에 남긴다. 승계값은 어제 값이라
        # 오늘 행으로 기록하면 다음 날 전일 대비가 통째로 거짓이 된다(design/08 §S3의 연장).
        if missing or carried:
            log.warning("Asset 발행(확보 %s · 승계 %s · 결측 %s) — 스냅샷 원장 기록 보류",
                        ",".join(covered), ",".join(carried) or "없음", ",".join(missing) or "없음")
        else:
            asset_snapshot_repository.append_snapshot(
                payload["total_assets_krw"],
                {a["role"]: a["balance_krw"] for a in accounts},
            )
            log.info("Asset 암호화 발행 완료 — 4계좌 전량 확보, 스냅샷 원장 기록")
    elif not covered:
        log.warning("Asset 계좌 4개 전부 결측 — 발행 skip(직전 발행물 유지, 신선도 규칙이 강등)")
    else:
        log.info("ASSET_PASSPHRASE 미설정 — Asset 암호화 발행 skip(결측 문법)")

    # 승계는 covered에 포함되므로 items만 보면 결측을 놓친다 — detail에 사실대로 나눠 적는다
    fresh = [r for r in covered if r not in carried]
    runlog.note("Asset Publish",
                items=len(fresh),
                detail=f"수집 {','.join(fresh) or '없음'} · 승계 {','.join(carried) or '없음'}"
                       f" · 결측 {','.join(missing) or '없음'} · 발행 {'O' if published else 'X'}")

    out = DOCS_DIR / "asset" / "index.html"
    return render(
        "pages/asset.html",
        {
            "root": "..",
            "nav": nav.context(active="asset"),
            "generated_at": fmt_kst(now_kst()) + " KST",
        },
        out,
    )
