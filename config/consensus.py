"""경제지표 예상치(컨센서스) 수동 입력 — 무료 소스 부재로 수기 관리(design/21 §2-2 축소 확정).

design/21 문서는 "수기 YAML 입력"이라 표현하지만, 이 프로젝트의 config/는 전부 순수 Python
딕셔너리이고(markets.py·keywords.py·entities.py 등) YAML 파서 의존성이 전혀 없다 — 이 파일
하나만을 위해 PyYAML을 새 의존성으로 추가하지 않고 기존 관례를 그대로 따른다. 형식만 다를 뿐
"미입력 시 열 생략"이라는 계약은 동일하다.

키 = FRED series_id, 값 = {"consensus": float, "as_of": "YYYY-MM-DD"(예상치를 등록한 날짜)}.
값이 없는 지표는 예상치 열 자체를 렌더링하지 않는다(빈칸 렌더 금지, N1 확장 적용).
"""
from __future__ import annotations

CONSENSUS: dict[str, dict] = {
    # 예시(비워둠 — 실사용 시 발표 전 컨센서스를 수기로 채운다):
    # "CPIAUCSL": {"consensus": 3.1, "as_of": "2026-07-15"},
}
