"""감사 기준(rubric) — "무엇을 개선으로 볼 것인가"의 단일 정의. design/26 §3-4.

`config/slo.py`가 **런타임 상태**의 정상 기준이라면, 이 파일은 **코드 품질**의 정상 기준이다.
둘 다 존재 이유가 같다 — 판정 기준을 LLM 프롬프트 안에 녹여 두면 실행마다 흔들린다.
Auditor 루틴 프롬프트(`ops/prompts/auditor.md`)와 원장(`utils/ledger.py`)이 여기 선언된
동일한 id 체계를 참조하므로, 발행된 이슈는 항상 어떤 기준으로 잡혔는지 역추적된다.

기준을 바꾸고 싶으면 프롬프트가 아니라 이 파일을 고친다.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 최적화 우선순위 ────────────────────────────────────────────────────────────
# 번호가 곧 우선순위다. 앞쪽(제거 계열)이 뒤쪽(최적화 계열)보다 먼저인 이유는,
# 지우면 되는 것을 최적화하는 게 가장 흔한 낭비이기 때문이다.

AXIS_REMOVE = "제거"      # 없애면 끝나는 것 — 가장 싸고 안전한 개선
AXIS_STRUCTURE = "구조"   # 설계·가독성
AXIS_RESOURCE = "자원"    # CPU·메모리·I/O·네트워크
AXIS_SAFETY = "안정성"    # 예외·로그·관측


@dataclass(frozen=True)
class Priority:
    id: str
    label: str
    axis: str
    hint: str = ""  # 이 저장소에서 특히 어디를 봐야 하는지


PRIORITIES: tuple[Priority, ...] = (
    Priority("P01", "중복 코드 제거", AXIS_REMOVE,
             "generators/*/generate.py의 수집→검증→저장 인라인 중복(design/25 §1-4)"),
    Priority("P02", "불필요한 함수 제거", AXIS_REMOVE),
    Priority("P03", "사용되지 않는 import 제거", AXIS_REMOVE),
    Priority("P04", "Dead Code 제거", AXIS_REMOVE,
             "v1 은퇴 잔재·미사용 설정 키"),
    Priority("P05", "중복 API 호출 제거", AXIS_REMOVE,
             "collectors 메모이즈가 실제로 먹는지 — pipelines 재호출 경로 확인"),
    Priority("P06", "불필요한 반복문 제거", AXIS_RESOURCE),
    Priority("P07", "복잡한 조건문 단순화", AXIS_STRUCTURE),
    Priority("P08", "가독성 향상", AXIS_STRUCTURE),
    Priority("P09", "메모리 사용량 감소", AXIS_RESOURCE),
    Priority("P10", "CPU 사용량 감소", AXIS_RESOURCE),
    Priority("P11", "네트워크 요청 최소화", AXIS_RESOURCE,
             "Session 재사용·타임아웃 정책·재시도. 외부 무료 API라 Rate Limit이 실제 제약"),
    Priority("P12", "디스크 I/O 최소화", AXIS_RESOURCE,
             "같은 JSON을 한 빌드에서 여러 번 읽는 경로"),
    Priority("P13", "캐싱 가능한 부분 캐싱", AXIS_RESOURCE,
             "design/25가 정의한 캐시 계층 계약과 정합하는지"),
    Priority("P14", "비동기 전환 제안", AXIS_RESOURCE, "제안만 — 정적 빌드라 도입 비용이 크다"),
    Priority("P15", "병렬처리 제안", AXIS_RESOURCE, "제안만"),
    Priority("P16", "데이터 구조 최적화", AXIS_RESOURCE, "list 선형탐색 → set/dict"),
    Priority("P17", "시간복잡도 개선", AXIS_RESOURCE),
    Priority("P18", "공간복잡도 개선", AXIS_RESOURCE),
    Priority("P19", "예외처리 개선", AXIS_SAFETY,
             "부분 실패 허용 원칙은 유지하되, 삼킨 예외가 runlog에 사실대로 남는지"),
    Priority("P20", "로그 개선", AXIS_SAFETY, "sync_auto.log 용량 관리 포함"),
)

PRIORITY_BY_ID: dict[str, Priority] = {p.id: p for p in PRIORITIES}

# ── 도메인 특화 점검 ───────────────────────────────────────────────────────────
# 일반 최적화 목록만으로는 이 저장소 고유의 함정(무료 API 예산·정적 발행·데스크톱 경계)을
# 놓친다. Auditor는 담당 영역에 해당하는 항목만 본다.

DOMAIN_CHECKS: tuple[str, ...] = (
    "데이터 수집 중복 제거",
    "HTTP 요청 최소화",
    "API Rate Limit 고려",
    "캐시 적용 가능 여부",
    "pandas 연산 최적화",
    "불필요한 DataFrame 복사 제거",
    "파일 읽기/쓰기 최소화",
    "Jinja2 렌더링 최적화",
    "GitHub Actions 실행 시간 단축",
    "로그 파일 용량 관리",
    "HTML/CSS/JS 용량 최적화",
    "Python 시작 속도·import 속도 개선",
    "메모리 누수 가능성 점검",
    "예외 처리 표준화",
    "설정(config) 중앙 관리",
    "환경변수 관리 개선",
    "타입 힌트 추가",
    "테스트 가능한 구조로 리팩토링",
)

# ── 원칙·안전 규칙 ────────────────────────────────────────────────────────────

PRINCIPLES: tuple[str, ...] = ("SOLID", "DRY", "KISS", "YAGNI")

# 위반 시 그 제안은 **폐기**한다. 성능보다 정확성·안정성이 우선이라는 뜻이다.
SAFETY_RULES: tuple[str, ...] = (
    "기존 기능을 깨뜨리지 않는다",
    "외부 API 동작을 변경하지 않는다",
    "입출력 형식(발행 JSON·Envelope·frontmatter 스키마)을 변경하지 않는다",
    "데이터 손실 가능성이 있는 수정은 하지 않는다",
    "기존 테스트는 전량 통과해야 한다",
    "가독성이 크게 떨어지는 과도한 최적화는 하지 않는다",
)

# 이슈 1건이 반드시 담아야 하는 필드 — 원장 스키마이자 vault 노트의 본문 구조다.
# "문제점만 있고 해결방법이 없는 지적"을 원천 차단하는 장치다.
REPORT_FIELDS: tuple[str, ...] = ("문제점", "원인", "해결방법", "성능향상", "부작용")

# ── 감사 영역 로테이션 (design/26 D-3 확정: 7영역/7주) ──────────────────────────
# 1세션에 실제로 다 훑을 수 있는 크기로 자른다. "전체 코드베이스"가 실패한 이유가 크기다.


@dataclass(frozen=True)
class Area:
    key: str
    paths: tuple[str, ...]
    focus: tuple[str, ...]  # 이 영역에서 특히 볼 우선순위 id


AREAS: tuple[Area, ...] = (
    Area("collectors", ("collectors/",), ("P05", "P11", "P13", "P19")),
    Area("validators", ("validators/", "schema/"), ("P07", "P19", "P01")),
    Area("repositories", ("repositories/", "models/"), ("P12", "P13", "P16")),
    Area("calculators", ("calculators/",), ("P06", "P16", "P17", "P18")),
    Area("generators", ("generators/", "templates/"), ("P01", "P12")),
    Area("build-ci", ("build.py", "app/", ".github/", "scripts/"), ("P10", "P20", "P04")),
    Area("tests-docs", ("tests/", "docs/", "static/", "design/"), ("P04", "P08")),
)

AREA_BY_KEY: dict[str, Area] = {a.key: a for a in AREAS}


def area_for_week(iso_week: int) -> Area:
    """ISO 주차 → 이번 주 감사 영역. 7영역이라 7주 1순환이며 빠지는 영역이 없다."""
    return AREAS[iso_week % len(AREAS)]
