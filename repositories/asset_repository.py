"""4계좌 자산 집계 + 암호화 발행(design/08, design/20 Phase 8 A안).

계좌 원장(수집기 raw) → 정규화 → 합계·비중·목표달성률(calculators/asset_indicators) → 전일
대비(로컬 스냅샷, asset_snapshot_repository) → PBKDF2+AES-GCM 암호화(utils/crypto) →
docs/data/asset/assets.enc.json. ASSET_PASSPHRASE 미설정이면 발행 자체를 skip한다 — 암호화
못 할 데이터를 평문으로 내보내느니 아예 발행하지 않는 것이 안전하다(design/20 Phase 8 DoD 1).
"""
from __future__ import annotations

from datetime import datetime, timezone

from calculators.asset_indicators import (
    covered_roles,
    currency_exposure,
    goal_progress_pct,
    total_assets,
    total_pnl,
    with_holding_weights,
    with_weights,
)
from config.settings import ASSET_GOAL_KRW, ASSET_PASSPHRASE, DOCS_DIR
from repositories import asset_snapshot_repository
from utils.crypto import encrypt
from utils.jsonio import save_json
from utils.logging import get_logger
from validators.asset_validator import parse_amount

log = get_logger("repo.asset")


def _day_change_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current / previous - 1) * 100, 2)


def _pnl_pct(pnl: float | None, value: float | None) -> float | None:
    """평가손익률 = 손익 / 매입원가. 원가 = 평가금액 − 손익(둘 다 있어야 계산)."""
    if pnl is None or value is None:
        return None
    cost = value - pnl
    return round(pnl / cost * 100, 2) if cost else None


def _rate_from_amounts(pnl: float | None, principal: float | None,
                       reported: float | None, *, what: str) -> float | None:
    """손익률은 **절대금액에서 계산한 값을 정본으로 삼는다**(design/25 §8-2).

    키움 opw00018의 `총수익률`을 그대로 쓰던 것이 화면에 -1718%를 띄운 원인이다 — KOA가 이
    필드를 100배 스케일(-1718 = -17.18%)로 돌려준다. 스케일 규칙을 추측해서 나누는 대신,
    이미 확보한 두 절대금액(평가손익·매입금액)에서 직접 계산한다. 소스가 어떤 스케일로
    바뀌어도 옳고, 두 금액은 화면의 다른 곳에서도 쓰이므로 이미 검증된 값이다.

    보고된 값은 교차검증용으로만 쓴다 — 어긋나면 로그로 남기되 화면은 계산값을 따른다.
    """
    if pnl is None or not principal:
        # 계산 재료가 없으면 결측으로 둔다. 스케일을 신뢰할 수 없는 보고값을 그대로
        # 내보내느니 손익률 행을 생략하는 편이 낫다(가짜 값 금지).
        if reported is not None:
            log.warning("%s: 매입금액 결측으로 손익률 계산 불가 — 보고값(%s)은 스케일 미검증이라 생략", what, reported)
        return None
    computed = round(pnl / principal * 100, 2)
    if reported is not None and abs(computed) > 0.01:
        ratio = reported / computed
        if not 0.5 < ratio < 2.0:
            log.warning("%s: 보고 손익률 %s vs 계산 %s%% (배율 %.1f배) — 계산값을 채택",
                        what, reported, computed, ratio)
    return computed


def _strip_kiwoom_code(raw: str) -> str:
    """KOA 종목번호는 'A005930'처럼 접두 문자가 붙어 온다 — 6자리 코드만 남긴다."""
    code = (raw or "").strip()
    return code[1:] if len(code) == 7 and code[0].isalpha() and code[1:].isdigit() else code


def _holding(code: str, name: str, *, quantity=None, avg_price=None, price=None,
             value_krw=None, value_usd=None, pnl=None, pnl_pct=None) -> dict:
    """보유종목 1행의 정규 형태(design/09 §3-4 열 구성). 없는 값은 None으로 남긴다."""
    return {
        "code": code, "name": name, "quantity": quantity,
        "avg_price": avg_price, "price": price,
        "value_krw": value_krw, "value_usd": value_usd,
        "eval_pnl_krw": pnl,
        "pnl_pct": pnl_pct if pnl_pct is not None else _pnl_pct(pnl, value_krw if value_krw is not None else value_usd),
    }


def _kiwoom_holdings(raw: dict | None) -> list[dict]:
    rows = (raw or {}).get("holdings") or []
    out = []
    for r in rows:
        value = parse_amount(r.get("평가금액"))
        code = _strip_kiwoom_code(r.get("종목코드", ""))
        if not code and value is None:
            continue
        qty = parse_amount(r.get("보유수량"))
        avg = parse_amount(r.get("매입가"))
        pnl = parse_amount(r.get("평가손익"))
        # 종목 수익률도 계좌 총수익률과 같은 스케일 문제를 안고 있다(design/25 §8-2) —
        # 매입원가(매입가 × 보유수량)에서 직접 계산하고, 재료가 없으면 _holding의
        # 평가금액−손익 폴백에 맡긴다(pnl_pct=None).
        cost = avg * qty if avg is not None and qty else None
        out.append(_holding(
            code, r.get("종목명", ""),
            quantity=qty, avg_price=avg,
            price=parse_amount(r.get("현재가")),
            value_krw=value,
            pnl=pnl,
            pnl_pct=_rate_from_amounts(pnl, cost, parse_amount(r.get("수익률")),
                                       what=f"키움 {r.get('종목명', code)} 수익률"),
        ))
    return out


def _kis_holdings(raw: dict | None, *, currency: str = "KRW") -> list[dict]:
    """KIS output1 필드명은 미검증(collectors/kis_collector.py 고지 참조) — 후보 필드로 최선 추출."""
    rows = (raw or {}).get("holdings") or []
    out = []
    for r in rows:
        name = r.get("prdt_name") or r.get("ovrs_item_name") or ""
        code = r.get("pdno") or r.get("ovrs_pdno") or ""
        value = parse_amount(r.get("evlu_amt") or r.get("ovrs_stck_evlu_amt"))
        if not name and value is None:
            continue
        pnl = parse_amount(r.get("evlu_pfls_amt") or r.get("ovrs_stck_evlu_pfls_amt")
                           or r.get("frcr_evlu_pfls_amt"))
        out.append(_holding(
            code, name,
            quantity=parse_amount(r.get("hldg_qty") or r.get("ovrs_cblc_qty")),
            avg_price=parse_amount(r.get("pchs_avg_pric")),
            price=parse_amount(r.get("prpr") or r.get("now_pric2")),
            value_krw=value if currency == "KRW" else None,
            value_usd=value if currency != "KRW" else None,
            pnl=pnl,
            pnl_pct=parse_amount(r.get("evlu_pfls_rt")),
        ))
    return out


def _bybit_holdings(raw: dict | None) -> list[dict]:
    coins = (raw or {}).get("coins") or []
    return [
        _holding(c.get("coin", ""), c.get("coin", ""),
                 quantity=c.get("wallet_balance"), value_usd=c.get("usd_value"))
        for c in coins if c.get("wallet_balance")
    ]


def _principal(balance: float | None, eval_pnl: float | None, reported: float | None = None) -> float | None:
    """투입 원금(design/08 Hero 3열). 수집기가 매입금액을 주면 그 값을, 없으면 평가액−손익."""
    if reported is not None:
        return reported
    if balance is None or eval_pnl is None:
        return None
    return round(balance - eval_pnl, 2)


def _securities_from_holdings(holdings: list[dict], key: str = "value_krw") -> float | None:
    """보유종목 평가금액 합계 — 계좌 요약의 '총평가금액'이 무엇을 포함하는지 판정하는 대조군."""
    values = [h[key] for h in holdings if h.get(key) is not None]
    return round(sum(values), 2) if values else None


def build_kiwoom_account(raw: dict | None, prev_krw: float | None) -> dict:
    """키움 계좌 — 예수금과 유가증권 평가액을 분리해 담는다(design/25 §8-3).

    opw00018의 `총평가금액`이 예수금을 포함하는지는 KOA 문서로 확정할 수 없어서, **보유종목
    평가금액 합계와 대조해 런타임에 판정한다**. 합계와 일치하면 유가증권만이라는 뜻이므로
    예수금을 더해 계좌 총액을 만들고, 이미 예수금이 섞여 있으면 그대로 총액으로 쓴다.
    추측 대신 확보한 데이터로 판정하는 방식이라 소스가 바뀌어도 조용히 틀리지 않는다.
    """
    s = (raw or {}).get("summary", {})
    holdings = with_holding_weights(_kiwoom_holdings(raw))
    reported_total = parse_amount(s.get("총평가금액"))
    deposit = parse_amount(s.get("예수금"))
    eval_pnl = parse_amount(s.get("총평가손익금액"))
    principal = _principal(reported_total, eval_pnl, parse_amount(s.get("총매입금액")))

    securities = _securities_from_holdings(holdings)
    deposit_included = _deposit_looks_included(reported_total, securities, deposit)
    if securities is None:
        securities = reported_total - deposit if (
            reported_total is not None and deposit is not None and deposit_included
        ) else reported_total
    balance = reported_total if deposit_included else _sum_present(securities, deposit)

    return {
        "role": "kiwoom", "label": "키움증권", "sub_label": "단타·스윙",
        "balance_krw": balance, "native_currency": "KRW",
        "change_pct": _day_change_pct(balance, prev_krw),
        "eval_pnl_krw": eval_pnl,
        # 총수익률 필드는 스케일 미검증(-1718% 사고의 원인) — 절대금액에서 계산한다.
        "eval_pnl_pct": _rate_from_amounts(eval_pnl, principal, parse_amount(s.get("총수익률")),
                                           what="키움 총수익률"),
        "principal_krw": principal,
        "securities_krw": securities,
        "deposit_krw": deposit,
        "deposit_in_balance": True,  # balance_krw는 위에서 항상 예수금 포함으로 맞춰진다
        "orderable_krw": parse_amount(s.get("주문가능금액")),
        "holdings": holdings,
    }


def _sum_present(*values) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present), 2) if present else None


def _securities_base(total: float | None, securities: float | None,
                     deposit: float | None) -> float | None:
    """원가 역산에 쓸 '유가증권만의 평가액'. 확보 순서: 명시값 → 총액−예수금 → 총액."""
    if securities is not None:
        return securities
    if total is not None and deposit is not None:
        return round(total - deposit, 2)
    return total


def _deposit_looks_included(total: float | None, securities: float | None,
                            deposit: float | None) -> bool:
    """`total`이 예수금을 이미 품고 있는가 — 두 후보식 중 어느 쪽에 더 가까운지로 판정.

    판정 불가(재료 결측)면 False를 돌려 '예수금을 더해야 한다'고 본다. 예수금이 결측이면
    더해도 값이 그대로라 무해하고, 실제로 빠져 있었을 때 총액이 적게 나오는 쪽이
    사용자가 겪은 문제(한투 위탁 -14.8%)였기 때문이다.
    """
    if total is None or securities is None or deposit is None:
        return False
    return abs(total - (securities + deposit)) < abs(total - securities)


def build_kis_isa_account(raw: dict | None, prev_krw: float | None) -> dict:
    raw = raw or {}
    balance = raw.get("krw_value")
    eval_pnl = raw.get("eval_pnl_krw")
    # 원가 역산의 기준은 유가증권 평가액이다 — krw_value는 예수금을 포함하므로(실측
    # tot_evlu_amt == evlu_amt_smtl_amt + dnca_tot_amt) 그걸로 역산하면 원가가 부풀어
    # 손익률이 실제보다 작게 나온다. 유가증권 평가액이 없으면 총액에서 예수금을 빼고,
    # 예수금마저 없으면 총액 그대로 쓴다(예수금 정보가 없는 소스에 대한 하위 호환).
    principal = _principal(_securities_base(balance, raw.get("securities_krw"), raw.get("deposit_krw")),
                           eval_pnl, raw.get("principal_krw"))
    return {
        "role": "kis_isa", "label": "한국투자 ISA", "sub_label": "ETF",
        "balance_krw": balance, "native_currency": "KRW",
        "change_pct": _day_change_pct(balance, prev_krw),
        "eval_pnl_krw": eval_pnl,
        "eval_pnl_pct": _rate_from_amounts(eval_pnl, principal, None, what="한투 ISA 손익률"),
        "principal_krw": principal,
        "deposit_krw": raw.get("deposit_krw"),
        "orderable_krw": raw.get("orderable_krw"),
        # KIS 국내 총평가금액은 예수금을 포함한다(실측) — 화면이 평가액과 예수금을 더해서
        # 읽히지 않도록 그 사실을 그대로 전달한다.
        "deposit_in_balance": raw.get("deposit_in_balance", False),
        "securities_krw": raw.get("securities_krw"),
        "holdings": with_holding_weights(_kis_holdings(raw, currency="KRW")),
    }


def build_kis_foreign_account(raw: dict | None, usdkrw: float | None, prev_krw: float | None) -> dict:
    raw = raw or {}
    usd_value = raw.get("usd_value")
    eval_pnl_usd = raw.get("eval_pnl_usd")
    securities_usd = raw.get("securities_usd")
    deposit_usd = raw.get("deposit_usd")
    balance_krw = round(usd_value * usdkrw, 2) if usd_value is not None and usdkrw else None
    # 매입원가는 **유가증권 기준**이다 — 예수금이 섞인 총액에서 역산하면 원가가 부풀어
    # 손익률이 실제보다 작게 나온다(usd_value는 이제 예수금 포함 총액이다).
    principal_usd = _principal(_securities_base(usd_value, securities_usd, deposit_usd),
                               eval_pnl_usd, raw.get("principal_usd"))
    return {
        "role": "kis_foreign", "label": "한국투자", "sub_label": "미국주식",
        "balance_krw": balance_krw, "native_currency": "USD",
        "usd_value": usd_value, "fx_rate": usdkrw,
        "change_pct": _day_change_pct(balance_krw, prev_krw),
        "eval_pnl_krw": round(eval_pnl_usd * usdkrw, 2) if eval_pnl_usd is not None and usdkrw else None,
        "eval_pnl_pct": _rate_from_amounts(eval_pnl_usd, principal_usd, None, what="한투 위탁 손익률"),
        "principal_usd": principal_usd,
        "principal_krw": round(principal_usd * usdkrw, 2) if principal_usd is not None and usdkrw else None,
        # design/25 §8-1: 예수금이 통째로 빠져 총액이 14.8% 적게 나오던 것을 별도 TR로 보강했다.
        "securities_usd": securities_usd,
        "securities_krw": round(securities_usd * usdkrw, 2) if securities_usd is not None and usdkrw else None,
        "deposit_usd": deposit_usd,
        "deposit_krw": round(deposit_usd * usdkrw, 2) if deposit_usd is not None and usdkrw else None,
        "deposit_in_balance": True,
        "holdings": with_holding_weights(_kis_holdings(raw, currency="USD")),
    }


def build_bybit_account(raw: dict | None, usdkrw: float | None, prev_krw: float | None) -> dict:
    raw = raw or {}
    usd_value = raw.get("total_equity_usd")
    balance_krw = round(usd_value * usdkrw, 2) if usd_value is not None and usdkrw else None
    return {
        "role": "bybit", "label": "BYBIT", "sub_label": "암호화폐",
        "balance_krw": balance_krw, "native_currency": "USDT",
        "usd_value": usd_value, "fx_rate": usdkrw,
        "change_pct": _day_change_pct(balance_krw, prev_krw),
        # Bybit v5 wallet-balance는 누적 평가손익을 주지 않는다(미검증 영역이 아니라 미제공) —
        # 없는 값을 만들지 않고 결측으로 두면 화면이 이 계좌의 손익 행을 통째로 생략한다.
        "eval_pnl_krw": None, "eval_pnl_pct": None, "principal_krw": None,
        "holdings": with_holding_weights(_bybit_holdings(raw)),
    }


def build_payload(accounts: list[dict]) -> dict:
    """암호화 대상 평문 payload(design/08 Hero+계좌 카드 재료). 이 dict를 절대 그대로 발행하지 않는다.

    부분 결측(계좌 일부만 확보)이면 total_assets_krw는 '확보분 합계'라는 뜻이므로
    missing_roles로 그 사실을 payload에 실어 보낸다 — 화면이 부분합을 총자산인 양
    렌더하지 않게 하는 근거다. 전일 대비도 같은 이유로 부분 결측일 땐 계산하지 않는다
    (어제는 4계좌, 오늘은 3계좌인 합계를 비교하면 순전히 결측 때문에 급락으로 보인다).
    """
    accounts = with_weights(accounts)
    current_total = total_assets(accounts)
    covered, missing = covered_roles(accounts)
    prev = asset_snapshot_repository.previous_snapshot()
    prev_total = (prev or {}).get("total_assets_krw")
    # 원장에는 완전한 행만 들어가므로(asset_snapshot_repository), 오늘이 완전하기만 하면
    # 어제와 같은 계좌 구성끼리 비교된다.
    comparable = not missing
    pnl, pnl_pct, principal = total_pnl(accounts)
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_assets_krw": current_total,
        "day_change_pct": _day_change_pct(current_total, prev_total) if comparable else None,
        "day_change_basis": (prev or {}).get("date") if comparable and prev else None,
        "total_pnl_krw": pnl,
        "total_pnl_pct": pnl_pct,
        "principal_krw": principal,
        "goal_amount_krw": ASSET_GOAL_KRW or None,
        "goal_progress_pct": goal_progress_pct(current_total, ASSET_GOAL_KRW) if not missing else None,
        "covered_roles": covered,
        "missing_roles": missing,
        "accounts": accounts,
        "currency_exposure": currency_exposure(accounts),
        "history": asset_snapshot_repository.history(90),
    }


def persist_encrypted(payload: dict) -> bool:
    """암호문 발행. False = 발행하지 않음(결측 문법의 연장).

    발행하지 않는 두 경우:
      1. ASSET_PASSPHRASE 미설정 — 암호화 못 할 데이터를 평문으로 내보내느니 발행하지 않는다.
      2. 확보 계좌 0건 — 내용이 전부 결측인 봉투를 덮어쓰면, 직전에 정상 발행된 스냅샷이
         '총자산 모름' 화면으로 대체된다. 수집이 통째로 실패한 날은 직전 발행물을 그대로
         두고 신선도 규칙(design/21 §6-2)이 DELAYED→STALE로 강등하게 두는 편이 정직하다.
    """
    if not ASSET_PASSPHRASE:
        return False
    if not payload.get("covered_roles"):
        return False
    envelope = encrypt(payload, ASSET_PASSPHRASE)
    save_json(DOCS_DIR / "data" / "asset" / "assets.enc.json", envelope)
    return True
