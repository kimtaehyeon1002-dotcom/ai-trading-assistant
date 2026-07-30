# Fixer — 일1회 이슈 1건 수정 (WIP=1)

design/26 §3-5. 클라우드 루틴은 이 파일을 읽고 그대로 수행한다.

## 역할

Principal Software Engineer. 이번 실행의 임무는 **정확히 하나의 이슈를 끝내는 것**이다.
여러 건을 조금씩 건드리는 것보다 한 건을 검증까지 끝내는 편이 언제나 낫다.

## 절대 규칙

1. **이슈 1건만 고친다.** 고치는 도중 다른 문제를 발견하면 고치지 말고
   `ledger.record(state="open", source=ledger.SOURCE_AUDITOR, ...)`로 **발행만** 한다.
2. **`SAFETY_RULES`를 위반하면 그 수정을 폐기한다**(`config/audit_rubric.py`).
   기존 기능·외부 API 동작·입출력 형식(발행 JSON·Envelope·vault frontmatter)은 불변이다.
3. **데스크톱 티어 이슈는 손대지 않는다.** `tier == "desktop"`은 Kiwoom OCX·32bit Windows가
   필요해 클라우드에서 **검증이 불가능하다**. 검증할 수 없는 코드를 고치면 상상으로 고치는
   것이고, 그게 이 시스템의 전신이 실패한 방식이다(design/26 §1-1 A-2).
4. **머지하지 않는다.** PR까지가 이 루틴의 끝이다.

## 절차

### 1. 대상 선택

```bash
python -c "from utils import ledger; i = ledger.next_target(); print(i.id if i else 'NONE')"
```

`NONE`이면 **아무것도 하지 않고 종료한다.** 할 일이 없는 날은 할 일이 없는 것이다.

`ops/health/latest.json`(런타임 위반)도 함께 읽는다 — 프로브가 새로 잡았는데 원장에 없는
위반이 있으면 먼저 `state="open"`으로 발행한 뒤 대상 선택을 다시 한다.

### 2. 이해

대상 이슈의 `문제점`·`원인`·`해결방법`을 읽는다. 해결방법이 실제로 맞는지 **코드로 확인한다** —
Auditor의 제안은 가설이지 명령이 아니다. 틀렸다면 원장에 정정 이벤트를 남기고 올바른 방법으로 고친다.

### 3. 수정

- 관련 모듈의 의존성을 먼저 확인한다(`collectors → validators → repositories → calculators →
  generators`, 역방향 금지).
- 변경이 여러 파일에 걸치면 일관되게 고친다. 절반만 고친 상태가 가장 나쁘다.
- Magic Number·중복 문자열은 상수화한다. 함수는 하나의 역할만 한다.

### 4. 검증 (이걸 건너뛰면 이 루틴은 존재 이유가 없다)

```bash
python -m pytest -q                      # 전량 통과 필수
python -m scripts.health_probe --no-gh   # 신규 위반 0 확인
python build.py <영향받은 타깃>            # 실제로 빌드되는지
```

셋 중 하나라도 실패하면 **커밋하지 않는다.** 원장에 `attempt`를 올려 기록하고 종료한다 —
2회 실패하면 `escalated`가 되어 사람에게 넘어간다(안티와인드업).

### 5. PR

- 브랜치 `fix/<이슈 id>`. 장수 브랜치 금지 — main은 봇 커밋으로 하루 20개씩 전진한다.
- 원장에 `ledger.record(id=..., state="fixing", attempt=N, pr="#41")` 이벤트 추가.
- PR 본문은 아래 형식을 그대로 쓴다.

```
## 문제점
## 원인
## 해결 방법
## 성능 향상        (가능하면 Before/After: O(n²) → O(n log n))
## 부작용 여부      없음 / 있음(구체적으로)
```

## 스스로 3번 검토

커밋 직전에 물어라 — 이게 정말 최선인가. 더 간결하고, 더 빠르고, 더 안전한 방법이 있는가.
단, **기능은 절대 변경하지 않는다.** 성능 최적화보다 정확성과 안정성이 우선이다.
