"""루프 원장 → Obsidian vault write-back. design/26 §3-8.

`ops/ledger.jsonl`(기계용 append-only)을 사람이 Obsidian에서 조회·복기할 수 있는 노트로
투영한다. 원장이 진실원이고 여기 노트는 **파생물**이다 — 매 빌드 재생성되며 멱등하다
(내용이 같으면 git diff가 없다).

쓰기 위치는 `50_Ops/`다. `10_Journal/`을 쓰지 않는 이유는 TH_DATA가 "Trading 장기기억
저장소"이고, 그 폴더의 Dataview 조회축(trade-journal/morning-report/news-digest)에 엔지니어링
이슈가 섞이면 매매 복기 쿼리가 오염되기 때문이다. 쓰기 주체 규칙은 동일하다 — **봇만** 쓴다.

20_Memory와 달리 사용자 가필을 보존하지 않는다(봇 전용 파생 폴더). 사람의 판단은 노트가 아니라
원장에 `wontfix` 이벤트로 남긴다 — 그래야 다음 실행이 그 판단을 읽는다.
"""
from __future__ import annotations

from pathlib import Path

from config.audit_rubric import PRIORITY_BY_ID, REPORT_FIELDS
from config.settings import VAULT_DIR
from utils import ledger
from utils.dates import now_kst
from utils.frontmatter import quote
from utils.logging import get_logger

log = get_logger("gen.vault_ops")

_OPS = VAULT_DIR / "50_Ops" / "loop"
_INDEX = _OPS / "INDEX.md"

# Dataview 조회축 계약 — TH_DATA/README.md의 `loop-issue` 행과 동기화해야 한다.
_TYPE = "loop-issue"

_INDEX_BODY = """
## 미해결 (심각도 순)

```dataview
TABLE severity AS 심각도, area AS 영역, 우선순위, state AS 상태, attempt AS 시도
FROM "50_Ops/loop"
WHERE type = "loop-issue" AND !contains(list("closed", "wontfix"), state)
SORT severity ASC, first_seen ASC
```

## 사람이 봐야 하는 것 (자동수정 포기)

```dataview
TABLE 문제점, attempt AS 시도횟수, last_seen AS 최종
FROM "50_Ops/loop"
WHERE type = "loop-issue" AND state = "escalated"
SORT last_seen DESC
```

## 우선순위별 누적

```dataview
TABLE length(rows) AS 건수, length(filter(rows.state, (s) => s = "closed")) AS 해결됨
FROM "50_Ops/loop"
WHERE type = "loop-issue"
GROUP BY 우선순위
SORT length(rows) DESC
```

## 최근 해결

```dataview
TABLE area AS 영역, 해결방법, last_seen AS 해결일
FROM "50_Ops/loop"
WHERE type = "loop-issue" AND state = "closed"
SORT last_seen DESC
LIMIT 20
```
"""


def enabled() -> bool:
    return VAULT_DIR.is_dir()


def _note(issue: ledger.Issue) -> str:
    priority = PRIORITY_BY_ID.get(issue.priority)
    lines = [
        "---",
        f"type: {_TYPE}",
        f"id: {quote(issue.id)}",
        f"title: {quote(issue.title)}",
        f"state: {issue.state}",
        f"severity: {issue.severity}",
        f"area: {issue.area}",
        f"source: {issue.source}",
        f"tier: {issue.tier}",
        f"attempt: {issue.attempt}",
        f"first_seen: {issue.first_seen[:10]}",
        f"last_seen: {issue.last_seen[:10]}",
    ]
    if priority:
        # 조회축 2개 — 기계용 id(priority)와 사람이 GROUP BY 할 라벨(우선순위)
        lines += [f"priority: {priority.id}", f"우선순위: {quote(priority.label)}"]
    if issue.pr:
        lines.append(f"pr: {quote(issue.pr)}")
    lines += ["---", f"# {issue.title or issue.id}", ""]

    for field in REPORT_FIELDS:
        value = issue.report.get(field)
        lines += [f"## {field}", "", value.strip() if value else "(미기재)", ""]

    lines += ["---", f"원장: `{issue.id}` · 진실원은 `ops/ledger.jsonl`이다(이 노트는 파생물)."]
    return "\n".join(lines) + "\n"


def _safe_name(issue_id: str) -> str:
    """이슈 id → 파일명. id는 이미 ascii 슬러그지만 경로 구분자만 방어한다."""
    return issue_id.replace("/", "-").replace("\\", "-")


def write_issues() -> list[Path]:
    """원장 전체를 노트로 재생성 → 50_Ops/loop/*.md + INDEX.md. 반환=쓰여진 경로들."""
    if not enabled():
        return []

    issues = ledger.state()
    if not issues:
        return []

    written: list[Path] = []
    for issue in issues.values():
        path = _OPS / f"{_safe_name(issue.id)}.md"
        text = _note(issue)
        # 멱등 — 내용이 같으면 쓰지 않는다(mtime만 바뀌어도 vault git이 커밋을 만든다)
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)

    counts = {s: sum(1 for i in issues.values() if i.state == s) for s in ledger.STATES}
    index = (
        "---\ntype: loop-index\n"
        f"updated: {now_kst().strftime('%Y-%m-%d %H:%M')}\n---\n"
        "# 루프 이슈 대장\n\n"
        f"총 {len(issues)}건 — "
        + " · ".join(f"{s} {n}" for s, n in counts.items() if n)
        + "\n\n기준: `config/audit_rubric.py`(코드 품질) · `config/slo.py`(런타임 상태). "
        "이 폴더는 봇 전용이며 원장(`ops/ledger.jsonl`)에서 매 빌드 재생성된다.\n"
        + _INDEX_BODY
    )
    if not _INDEX.exists() or _INDEX.read_text(encoding="utf-8") != index:
        _INDEX.parent.mkdir(parents=True, exist_ok=True)
        _INDEX.write_text(index, encoding="utf-8")
        written.append(_INDEX)

    if written:
        log.info("루프 이슈 vault 기록: %d건 갱신(전체 %d건)", len(written), len(issues))
    return written
