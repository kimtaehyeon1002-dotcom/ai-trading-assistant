"""루프 원장 — 문제점→해결방법의 누적 기록. design/26 §3-3.

이 파일이 루프의 **적분항**이다. 세션은 매번 죽으므로, 어제 무엇을 찾았고 무엇을 시도했다
실패했는지는 저장소 안에 남아야 한다. 원장이 없으면 매 실행이 0에서 시작해 수렴하지 않는다
(현행 「th_bot 전체 코드 점검」 루틴이 실패한 이유 B-1).

형식은 append-only JSONL이다. 봇 커밋이 30~60분 간격으로 나는 main에서 **줄 추가만** 하면
git 충돌이 사실상 나지 않는다(같은 줄을 고치지 않으므로). 현재 상태는 이벤트를 접어서 얻는다.

    record(id=..., state="open", 문제점=..., 해결방법=...)   # 이벤트 1줄 추가
    state()                                                  # id → 최신 상태(폴드 결과)
    next_target()                                            # 지금 고칠 이슈 1건(WIP=1)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.audit_rubric import REPORT_FIELDS
from config.settings import BASE_DIR
from config.slo import SEVERITY_ORDER
from utils.dates import now_kst

LEDGER_PATH = BASE_DIR / "ops" / "ledger.jsonl"

# 아래 함수들의 path 기본값이 `= LEDGER_PATH`가 아니라 `= None`인 이유: 기본 인자는 def
# 시점에 한 번 평가되므로 상수를 박아두면 테스트에서 monkeypatch가 먹지 않는다. 호출 시점에
# 해석해야 원장 경로를 갈아끼울 수 있다(테스트 가능한 구조 — audit_rubric DOMAIN_CHECKS).

# 상태기계 — open에서 시작해 closed 또는 escalated/wontfix에서 멈춘다.
STATE_OPEN = "open"            # 발행됨, 아직 손 안 댐
STATE_FIXING = "fixing"        # 수정 PR 생성됨
STATE_VERIFYING = "verifying"  # CI 검증 대기
STATE_CLOSED = "closed"        # 검증 통과 후 머지됨
STATE_ESCALATED = "escalated"  # 자동수정 포기 — 사람 대기
STATE_WONTFIX = "wontfix"      # 사람이 "안 고침"으로 판단(오탐 포함)

STATES = (STATE_OPEN, STATE_FIXING, STATE_VERIFYING, STATE_CLOSED, STATE_ESCALATED, STATE_WONTFIX)
ACTIVE_STATES = (STATE_OPEN, STATE_FIXING, STATE_VERIFYING)
TERMINAL_STATES = (STATE_CLOSED, STATE_ESCALATED, STATE_WONTFIX)

# 안티와인드업 — 같은 이슈를 이 횟수만큼 시도해 실패하면 자동수정을 멈춘다.
# 이게 없으면 구조적으로 못 고치는 이슈(예: 클라우드에서 Kiwoom 실행)에 매 실행을 태운다.
MAX_ATTEMPTS = 2

# 이슈를 만든 주체 — 오탐률을 주체별로 집계해야 어느 쪽 기준을 조일지 알 수 있다.
SOURCE_PROBE = "probe"      # scripts/health_probe.py (결정론적)
SOURCE_AUDITOR = "auditor"  # Auditor 루틴 (LLM, 설계문서·rubric 대비)
SOURCE_HUMAN = "human"


@dataclass(frozen=True)
class Issue:
    """폴드된 현재 상태 1건."""

    id: str
    title: str
    state: str
    severity: str
    source: str
    area: str
    priority: str      # config/audit_rubric.PRIORITIES의 id (예: "P11"), 프로브 발행 건은 ""
    tier: str
    attempt: int
    pr: str
    first_seen: str
    last_seen: str
    report: dict[str, str]  # REPORT_FIELDS

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def severity_rank(self) -> int:
        try:
            return SEVERITY_ORDER.index(self.severity)
        except ValueError:
            return len(SEVERITY_ORDER)


def record(
    *,
    id: str,  # noqa: A002 - 원장 필드명이 id다(shadowing보다 스키마 일치가 중요)
    state: str,
    title: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    area: str | None = None,
    priority: str | None = None,
    tier: str | None = None,
    attempt: int | None = None,
    pr: str | None = None,
    path: Path | None = None,
    **report: str,
) -> dict[str, Any]:
    """이벤트 1건 append. `report`는 REPORT_FIELDS(문제점/원인/해결방법/성능향상/부작용).

    **기술 필드의 기본값은 전부 None이다** — 상태 전이 이벤트(`state="closed"`)가 기본값을
    함께 실어 나르면, 최초 발행 때의 severity·tier를 조용히 덮어쓴다. 실제로 그렇게 만들었다가
    critical 이슈가 closed 전이에서 major로 바뀌는 것을 확인했다. 명시한 것만 기록한다.

    선언되지 않은 report 키는 조용히 버리지 않고 예외를 낸다 — 오타 난 필드가 vault에서
    영영 안 보이는 것보다 지금 터지는 편이 낫다.
    """
    path = path or LEDGER_PATH
    if state not in STATES:
        raise ValueError(f"알 수 없는 state: {state} (choices: {STATES})")
    unknown = set(report) - set(REPORT_FIELDS)
    if unknown:
        raise ValueError(f"알 수 없는 리포트 필드: {sorted(unknown)} (choices: {REPORT_FIELDS})")

    event: dict[str, Any] = {"ts": now_kst().isoformat(), "id": id, "state": state}
    for key, value in (("title", title), ("severity", severity), ("source", source),
                       ("area", area), ("priority", priority), ("tier", tier), ("pr", pr)):
        if value is not None:
            event[key] = value
    if attempt is not None:
        event["attempt"] = attempt
    event.update({k: v for k, v in report.items() if v})

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def events(path: Path | None = None) -> list[dict]:
    """기록 순서 그대로. 깨진 줄은 건너뛴다(한 줄 손상이 원장 전체를 못 읽게 만들면 안 된다)."""
    path = path or LEDGER_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return []
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("id"):
            out.append(parsed)
    return out


def state(path: Path | None = None) -> dict[str, Issue]:
    """이벤트를 접어 id별 현재 상태로. 나중 이벤트가 명시한 필드만 덮어쓴다.

    부분 갱신을 허용하는 이유: 상태 전이 이벤트(`state="fixing"`)가 문제점 본문을 다시
    실어 나를 필요가 없다. 원장이 얇아지고, 본문 재작성 과정의 변질도 막는다.
    """
    folded: dict[str, dict] = {}
    for e in events(path):
        cur = folded.setdefault(e["id"], {"first_seen": e["ts"], "report": {}})
        cur["last_seen"] = e["ts"]
        for key, value in e.items():
            if key in REPORT_FIELDS:
                cur["report"][key] = value
            elif key == "source":
                # source는 **최초 발견자**를 뜻한다(주체별 오탐률 집계축). 이후 전이 이벤트의
                # 행위자가 덮어쓰면 "누가 찾았나"가 사라지므로 first-wins다.
                cur.setdefault("source", value)
            elif key != "ts":
                cur[key] = value

    result: dict[str, Issue] = {}
    for issue_id, d in folded.items():
        result[issue_id] = Issue(
            id=issue_id,
            title=d.get("title", ""),
            state=d.get("state", STATE_OPEN),
            severity=d.get("severity", "major"),
            source=d.get("source", SOURCE_AUDITOR),
            area=d.get("area", ""),
            priority=d.get("priority", ""),
            tier=d.get("tier", "cloud"),
            attempt=int(d.get("attempt", 0)),
            pr=d.get("pr", ""),
            first_seen=d["first_seen"],
            last_seen=d.get("last_seen", d["first_seen"]),
            report=d["report"],
        )
    return result


def active(path: Path | None = None) -> list[Issue]:
    """미해결 이슈 — 심각도 → 먼저 발견된 순. 오래 방치된 건이 뒤로 밀리지 않게 한다."""
    return sorted(
        (i for i in state(path).values() if i.is_active),
        key=lambda i: (i.severity_rank, i.first_seen),
    )


def next_target(path: Path | None = None) -> Issue | None:
    """Fixer가 이번 실행에 고칠 이슈 1건(WIP=1). 없으면 None → 루틴은 아무것도 하지 않는다.

    데스크톱 티어는 제외한다 — 클라우드 세션이 검증할 수 없는 것을 고치게 두면,
    「run_bat 점검」 루틴이 그랬듯 상상으로 코드를 고친다(design/26 §1-1 A-2).
    """
    for issue in active(path):
        if issue.tier == "cloud" and issue.attempt < MAX_ATTEMPTS:
            return issue
    return None


def should_escalate(issue: Issue) -> bool:
    """재시도 상한 도달 — 자동수정을 멈추고 사람에게 넘길 때다."""
    return issue.is_active and issue.attempt >= MAX_ATTEMPTS
