"""DART(전자공시) 재무제표 수집 — 한국 상장사(design/20 Phase 7, design/21 §226).

무료 키 발급 필요(https://opendart.fss.or.kr). 미설정 시 수집 skipped(결측 문법, FRED/ECOS와
동일 원칙 — 가짜 데이터를 만들지 않는다). ⚠ 이 세션 환경에는 DART_API_KEY가 없어 실제 API
응답으로 검증하지 못했다 — 필드명(account_nm/thstrm_amount 등)은 DART 공식 문서 기준이며,
키 발급 후 반드시 라이브 재검증이 필요하다(design/21 §226 "공식 아님" 경고와 별개로, 이 필드
스키마 자체의 실측 확인이 아직 없다는 뜻).
"""
from __future__ import annotations

from config.settings import DART_API_KEY
from utils.logging import get_logger

log = get_logger("collectors.dart")

_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_FINANCIALS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

# IFRS 표준계정코드(account_id)로 매칭한다 — 계정과목명(account_nm)은 회사마다 표기가 갈리지만
# 표준코드는 고정이다. 실측 확인(2026-08-11, SK하이닉스 000660 2025년 CFS, 230행):
#   "영업이익"·"당기순이익"·"영업활동현금흐름"은 이름으로 찾으면 전부 빗나간다 — 실제 표기는
#   "영업이익(손실)"·"당기순이익(손실)"·"영업활동 현금흐름"(공백 포함)이다. EPS도 마찬가지로
#   "기본주당순이익(손실)"이라 이름 후보를 아무리 넓혀도 새는 구멍이 남는다.
# CAPEX는 현금유출을 양수로 기록한다(유형자산의 취득 27.5조) — EDGAR와 같은 부호라 FCF = OCF − CAPEX 그대로.
_ACCOUNT_IDS: dict[str, tuple[str, ...]] = {
    "revenue": ("ifrs-full_Revenue",),
    "operating_income": ("dart_OperatingIncomeLoss",),
    "net_income": ("ifrs-full_ProfitLoss",),
    "assets": ("ifrs-full_Assets",),
    "liabilities": ("ifrs-full_Liabilities",),
    "equity": ("ifrs-full_Equity",),
    "operating_cf": ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
    "capex": ("ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
    "eps": ("ifrs-full_BasicEarningsLossPerShare",),
}

# 표준코드를 쓰지 않는 행이 소수 존재한다(위 실측에서 230행 중 4행이 "-표준계정코드 미사용-").
# 그 경우에만 계정명으로 한 번 더 찾는다 — 이름 매칭은 폴백이지 주 경로가 아니다.
_ACCOUNT_NAMES: dict[str, tuple[str, ...]] = {
    "revenue": ("매출액", "수익(매출액)", "영업수익"),
    "operating_income": ("영업이익(손실)", "영업이익"),
    "net_income": ("당기순이익(손실)", "당기순이익"),
    "assets": ("자산총계",),
    "liabilities": ("부채총계",),
    "equity": ("자본총계",),
    "operating_cf": ("영업활동 현금흐름", "영업활동현금흐름"),
    "capex": ("유형자산의 취득",),
    "eps": ("기본주당순이익(손실)", "기본주당이익(손실)", "기본주당순이익", "주당순이익"),
}

_memo_corp_codes: dict[str, str] | None = None


def enabled() -> bool:
    return bool(DART_API_KEY)


def collect_corp_codes() -> dict[str, str] | None:
    """{stock_code(6자리): corp_code(8자리)} — corpCode.xml(zip) 파싱. 실행당 1회 캐시."""
    global _memo_corp_codes
    if not enabled():
        return None
    if _memo_corp_codes is not None:
        return _memo_corp_codes
    try:
        import io
        import xml.etree.ElementTree as ET
        import zipfile

        import requests

        r = requests.get(_CORP_CODE_URL, params={"crtfc_key": DART_API_KEY}, timeout=30)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            xml_bytes = zf.read(zf.namelist()[0])
        root = ET.fromstring(xml_bytes)
        out: dict[str, str] = {}
        for item in root.findall("list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if stock_code:
                out[stock_code] = corp_code
        _memo_corp_codes = out
    except Exception as exc:  # noqa: BLE001
        log.warning("DART corpCode 수집 실패: %s", exc)
        _memo_corp_codes = None
    return _memo_corp_codes


def _match_line(row: dict) -> str | None:
    """표준계정코드로 먼저 찾고, 그 코드가 없는 행만 계정명으로 폴백한다."""
    account_id = (row.get("account_id") or "").strip()
    if account_id and not account_id.startswith("-"):
        for line, ids in _ACCOUNT_IDS.items():
            if account_id in ids:
                return line
        return None
    account_nm = (row.get("account_nm") or "").strip()
    for line, names in _ACCOUNT_NAMES.items():
        if account_nm in names:
            return line
    return None


def collect_financials(corp_code: str, year: int) -> dict[str, list[dict]] | None:
    """{line: [{'year','value'}, ...]} 최근 5년(연결 기준) — 비활성화 시 None."""
    if not enabled():
        return None
    import requests

    lines: dict[str, list[dict]] = {k: [] for k in _ACCOUNT_IDS}
    for y in range(year - 4, year + 1):
        try:
            r = requests.get(_FINANCIALS_URL, params={
                "crtfc_key": DART_API_KEY, "corp_code": corp_code,
                "bsns_year": str(y), "reprt_code": "11011", "fs_div": "CFS",
            }, timeout=20)
            r.raise_for_status()
            body = r.json()
            if body.get("status") != "000":
                continue
            for row in body.get("list", []):
                amount = row.get("thstrm_amount", "")
                if not amount:
                    continue
                line = _match_line(row)
                if line is None or any(r["year"] == str(y) for r in lines[line]):
                    continue  # 같은 계정이 여러 재무제표에 중복 노출된다 — 연도당 첫 값만 취한다
                try:
                    lines[line].append({"year": str(y), "value": float(amount.replace(",", ""))})
                except ValueError:
                    pass
        except Exception as exc:  # noqa: BLE001 - 연도 단위 부분 실패 허용
            log.warning("DART 재무제표 수집 실패(연도=%s): %s", y, exc)
    return lines
