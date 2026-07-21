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

# DART 표준 계정과목명 — 회사별 상세 계정명이 다를 수 있어 완전 일치 실패 시 해당 연도만 결측.
_ACCOUNT_MAP: dict[str, str] = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "assets": "자산총계",
    "liabilities": "부채총계",
    "equity": "자본총계",
    "operating_cf": "영업활동현금흐름",
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


def collect_financials(corp_code: str, year: int) -> dict[str, list[dict]] | None:
    """{line: [{'year','value'}, ...]} 최근 5년(연결 기준) — 비활성화 시 None."""
    if not enabled():
        return None
    import requests

    lines: dict[str, list[dict]] = {k: [] for k in _ACCOUNT_MAP}
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
                account = row.get("account_nm", "")
                amount = row.get("thstrm_amount", "")
                if not amount:
                    continue
                for line, label in _ACCOUNT_MAP.items():
                    if account == label:
                        try:
                            lines[line].append({"year": str(y), "value": float(amount.replace(",", ""))})
                        except ValueError:
                            pass
        except Exception as exc:  # noqa: BLE001 - 연도 단위 부분 실패 허용
            log.warning("DART 재무제표 수집 실패(연도=%s): %s", y, exc)
    return lines
