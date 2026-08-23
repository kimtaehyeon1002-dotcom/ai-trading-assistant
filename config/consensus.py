"""경제지표 예상치(컨센서스) 수동 입력 — 무료 소스 부재로 수기 관리(design/21 §2-2 축소 확정).

design/21 문서는 "수기 YAML 입력"이라 표현하지만, 이 프로젝트의 config/는 전부 순수 Python
딕셔너리이고(markets.py·keywords.py·entities.py 등) YAML 파서 의존성이 전혀 없다 — 이 파일
하나만을 위해 PyYAML을 새 의존성으로 추가하지 않고 기존 관례를 그대로 따른다. 형식만 다를 뿐
"미입력 시 열 생략"이라는 계약은 동일하다.

키 = FRED series_id, 값 = {"value": float, "as_of": "YYYY-MM-DD"(예상치를 등록한 날짜)}.
값이 없는 지표는 예상치 열 자체를 렌더링하지 않는다(빈칸 렌더 금지, N1 확장 적용).

★ 필드명은 반드시 "value"다(Envelope와 같은 관례). 이 독스트링은 원래 "consensus"라고 적혀
있었고 템플릿은 `item.consensus.value`를 읽고 있어 **서로 어긋나 있었다** — 표가 비어 있어
아무도 밟지 않았을 뿐이다. Jinja 기본 Undefined는 조용히 빈 문자열이 되므로, 예시대로 채웠다면
"예상  (2026-07-15 등록)"처럼 숫자만 사라진 줄이 발행됐을 것이다(실측 확인 2026-08-14).
"""
from __future__ import annotations

CONSENSUS: dict[str, dict] = {
    # 예시(비워둠 — 실사용 시 발표 전 컨센서스를 수기로 채운다):
    # "CPIAUCSL": {"value": 3.1, "as_of": "2026-07-15"},
}
