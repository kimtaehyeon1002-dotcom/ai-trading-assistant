"""4계좌 자산 집계 + 암호화 발행(design/08, design/20 Phase 8 A안).

계좌 원장(수집기 raw) → 정규화 → 합계·비중·목표달성률(calculators/asset_indicators) → 전일
대비(로컬 스냅샷, asset_snapshot_repository) → PBKDF2+AES-GCM 암호화(utils/crypto) →
docs/data/asset/assets.enc.json. ASSET_PASSPHRASE 미설정이면 발행 자체를 skip한다 — 암호화
못 할 데이터를 평문으로 내보내느니 아예 발행하지 않는 것이 안전하다(design/20 Phase 8 DoD 1).
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators.asset_indicators import currency_exposure, goal_progress_pct, total_assets, with_weights
from config.settings import ASSET_GOAL_KRW, ASSET_PASSPHRASE, DOCS_DIR
from repositories import asset_snapshot_repository
from utils.crypto import encrypt
from utils.jsonio import save_json
from validators.asset_validator import parse_amount


def _day_change_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current / previous - 1) * 100, 2)


def _kiwoom_holdings(raw: dict | None) -> list[dict]:
    rows = (raw or {}).get("holdings") or []
    out = []
    for r in rows:
        qty = parse_amount(r.get("보유수량"))
        value = parse_amount(r.get("평가금액"))
        pnl = parse_amount(r.get("평가손익"))
        if not r.get("종목코드") and value is None:
            continue
        out.append({"code": r.get("종목코드", ""), "name": r.get("종목명", ""), "quantity": qty,
                    "value_krw": value, "eval_pnl_krw": pnl})
    return out


def _kis_holdings(raw: dict | None) -> list[dict]:
    """KIS output1 필드명은 미검증(collectors/kis_collector.py 고지 참조) — 후보 필드로 최선 추출."""
    rows = (raw or {}).get("holdings") or []
    out = []
    for r in rows:
        name = r.get("prdt_name") or r.get("ovrs_item_name") or ""
        code = r.get("pdno") or r.get("ovrs_pdno") or ""
        qty = parse_amount(r.get("hldg_qty") or r.get("ovrs_cblc_qty"))
        value = parse_amount(r.get("evlu_amt") or r.get("ovrs_stck_evlu_amt"))
        pnl = parse_amount(r.get("evlu_pfls_amt") or r.get("ovrs_stck_evlu_pfls_amt"))
        if not name and value is None:
            continue
        out.append({"code": code, "name": name, "quantity": qty, "value_krw": value, "eval_pnl_krw": pnl})
    return out


def _bybit_holdings(raw: dict | None) -> list[dict]:
    coins = (raw or {}).get("coins") or []
    return [
        {"code": c.get("coin", ""), "name": c.get("coin", ""), "quantity": c.get("wallet_balance"),
         "value_usd": c.get("usd_value"), "eval_pnl_krw": None}
        for c in coins if c.get("wallet_balance")
    ]


def build_kiwoom_account(raw: dict | None, prev_krw: float | None) -> dict:
    s = (raw or {}).get("summary", {})
    balance = parse_amount(s.get("총평가금액"))
    return {
        "role": "kiwoom", "label": "키움증권", "sub_label": "단타·스윙",
        "balance_krw": balance, "native_currency": "KRW",
        "change_pct": _day_change_pct(balance, prev_krw),
        "eval_pnl_krw": parse_amount(s.get("총평가손익금액")),
        "eval_pnl_pct": parse_amount(s.get("총수익률")),
        "holdings": _kiwoom_holdings(raw),
    }


def build_kis_isa_account(raw: dict | None, prev_krw: float | None) -> dict:
    balance = (raw or {}).get("krw_value")
    eval_pnl = (raw or {}).get("eval_pnl_krw")
    return {
        "role": "kis_isa", "label": "한국투자 ISA", "sub_label": "ETF",
        "balance_krw": balance, "native_currency": "KRW",
        "change_pct": _day_change_pct(balance, prev_krw),
        "eval_pnl_krw": eval_pnl,
        "eval_pnl_pct": _day_change_pct(balance, balance - eval_pnl) if balance is not None and eval_pnl is not None else None,
        "holdings": _kis_holdings(raw),
    }


def build_kis_foreign_account(raw: dict | None, usdkrw: float | None, prev_krw: float | None) -> dict:
    usd_value = (raw or {}).get("usd_value")
    eval_pnl_usd = (raw or {}).get("eval_pnl_usd")
    balance_krw = round(usd_value * usdkrw, 2) if usd_value is not None and usdkrw else None
    return {
        "role": "kis_foreign", "label": "한국투자", "sub_label": "미국주식",
        "balance_krw": balance_krw, "native_currency": "USD",
        "usd_value": usd_value, "fx_rate": usdkrw,
        "change_pct": _day_change_pct(balance_krw, prev_krw),
        "eval_pnl_krw": round(eval_pnl_usd * usdkrw, 2) if eval_pnl_usd is not None and usdkrw else None,
        "eval_pnl_pct": (
            round(eval_pnl_usd / (usd_value - eval_pnl_usd) * 100, 2)
            if usd_value is not None and eval_pnl_usd is not None and (usd_value - eval_pnl_usd) else None
        ),
        "holdings": _kis_holdings(raw),
    }


def build_bybit_account(raw: dict | None, usdkrw: float | None, prev_krw: float | None) -> dict:
    usd_value = (raw or {}).get("total_equity_usd")
    balance_krw = round(usd_value * usdkrw, 2) if usd_value is not None and usdkrw else None
    return {
        "role": "bybit", "label": "BYBIT", "sub_label": "암호화폐",
        "balance_krw": balance_krw, "native_currency": "USDT",
        "usd_value": usd_value,
        "change_pct": _day_change_pct(balance_krw, prev_krw),
        "eval_pnl_krw": None, "eval_pnl_pct": None,  # Bybit v5는 총평가손익을 직접 제공하지 않음(미검증 영역)
        "holdings": _bybit_holdings(raw),
    }


def build_payload(accounts: list[dict]) -> dict:
    """암호화 대상 평문 payload(design/08 Hero+계좌 카드 재료). 이 dict를 절대 그대로 발행하지 않는다."""
    accounts = with_weights(accounts)
    current_total = total_assets(accounts)
    prev = asset_snapshot_repository.previous_snapshot()
    prev_total = (prev or {}).get("total_assets_krw")
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_assets_krw": current_total,
        "day_change_pct": _day_change_pct(current_total, prev_total),
        "goal_amount_krw": ASSET_GOAL_KRW or None,
        "goal_progress_pct": goal_progress_pct(current_total, ASSET_GOAL_KRW),
        "accounts": accounts,
        "currency_exposure": currency_exposure(accounts),
        "history": asset_snapshot_repository.history(90),
    }


def persist_encrypted(payload: dict) -> bool:
    """ASSET_PASSPHRASE 미설정이면 발행하지 않고 False 반환(결측 문법의 연장)."""
    if not ASSET_PASSPHRASE:
        return False
    envelope = encrypt(payload, ASSET_PASSPHRASE)
    save_json(DOCS_DIR / "data" / "asset" / "assets.enc.json", envelope)
    return True
