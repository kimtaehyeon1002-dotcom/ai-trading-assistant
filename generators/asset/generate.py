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


def _kiwoom_balance() -> dict | None:
    """키움 잔고 — app/sync.py가 등록한 공유 세션을 우선 재사용(로그인 1회 원칙)."""
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


def generate() -> Path:
    kiwoom_raw = runlog.run_step("Asset Kiwoom", _kiwoom_balance, fallback=None)

    from collectors import bybit_collector, kis_collector

    kis_foreign_raw = runlog.run_step("Asset KIS 위탁", kis_collector.collect_overseas_balance, fallback=None)
    kis_isa_raw = runlog.run_step("Asset KIS ISA", kis_collector.collect_isa_balance, fallback=None)
    bybit_raw = runlog.run_step("Asset BYBIT", bybit_collector.collect_wallet_balance, fallback=None)

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

    payload = asset_repository.build_payload(accounts)
    covered, missing = payload["covered_roles"], payload["missing_roles"]
    published = asset_repository.persist_encrypted(payload)

    if published:
        # 완전 수집(4계좌 전량)일 때만 원장에 남긴다 — 부분 결측 합계를 기록하면 다음 날
        # 전일 대비가 결측을 자산 급락으로 보여준다(design/08 §S3 기준 병기 원칙의 연장).
        if missing:
            log.warning("Asset 발행(부분 확보 %s · 결측 %s) — 스냅샷 원장 기록 보류",
                        ",".join(covered), ",".join(missing))
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

    runlog.note("Asset Publish",
                items=len(covered),
                detail=f"확보 {','.join(covered) or '없음'} · 결측 {','.join(missing) or '없음'}"
                       f" · 발행 {'O' if published else 'X'}")

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
