# 26. 자가점검·자가수정 루프 (Loop Engineering) — 현행 루틴 감사와 설계

TH_BOT의 봇(GitHub Actions 6종 · 워커 20종 · 데스크톱 수집기)을 **루틴(cloud routine)으로 점검하고
수정하는 시스템**의 설계. 제어공학의 폐루프(closed loop) 구조를 그대로 옮긴다 —
**기준(SLO) → 측정(probe) → 오차(violation) → 적분항(ledger) → 제어(LLM) → 구동(PR) → 재측정(verify)**.

코드는 아직 수정하지 않았다. 본 문서 승인 후 Phase 단위로 구현한다(design/23·24·25와 동일 절차).

핵심 결론: 현재 등록된 루틴 2개는 **개루프(open loop)** 다. 측정값도, 기준값도, 이전 실행의 기억도,
수정이 실제로 통했는지 판정하는 게이트도 없다. 그래서 "매일 도는 랜덤워크"가 되어 있고, 그중 하나는
**클라우드에서 물리적으로 실행 불가능한 일**을 시키고 있다.

---

## 0. 검증된 현행 앵커 사실

실제 API·파일 확인 결과이며 설계의 전제다.

| 항목 | 확인된 사실 |
|---|---|
| 클라우드 루틴 | 2개 등록·enabled (아래 §1) |
| 로컬 예약작업 | `thbot-phase4-trading-coach` 1개(일회성, 2026-06-24 발화 후 disabled) — 사실상 없음 |
| GitHub Actions | 6종 — morning(21:30 UTC 일~목) · news(*/30) · macro(매시) · stock(장중 매시+마감+US) · financials(21:00 UTC) · trades(push 트리거) |
| 측정 자료(있음) | `utils/runlog.py` → `docs/ai-office/runlog.json`, 워커 20종의 `status/last_run/items/duration_ms/last_error` 기록 중 |
| 상태 어휘 | `completed | error | skipped` (정적 사이트라 running 없음) |
| 검증 자료(있음) | `tests/` 30개 파일, `validators/` 7종, `scripts/check_no_plaintext_assets.py` |
| main 커밋 빈도 | 봇 커밋 30~60분 간격(`chore(news)/chore(stock)/chore(macro)`) — 하루 약 20커밋 |
| Actions 동시성 | 전 워크플로 `concurrency: group: pages-commit` 공유 |
| 데스크톱 전용 경계 | Kiwoom OCX = 32bit Windows + `.venv32` + `.env`(gitignored). `run_desktop.bat`은 **클라우드에서 실행 불가** |

**측정 자료는 이미 있는데 루틴이 그걸 안 읽는다** — 이것이 현행 구조의 한 문장 요약이다.

---

## 1. 현행 루틴 감사

### 1-1. 「run_bat 점검」 `trig_01UAhQuwkMShBTJ1C1sSgkx3`

```
cron  : 0 22 * * 0-4 (UTC) = 07:00 KST 월~금
model : claude-opus-5,  repo: kimtaehyeon1002-dotcom/ai-trading-assistant
prompt: 매일 7:00am 21:00pm 한번씩 / run_desktop.bat 실행하기 / 문제없이 실행되는지 체크
        (asset관련 / 모닝리포트관련) / 문제가 생길시 수정 / 수정후 제대로 작동하는지 확인
outcome branch: claude/gracious-volta
```

| # | 문제 | 근거 | 등급 |
|---|---|---|---|
| A-1 | **실행 불가한 작업을 지시** — 클라우드 세션은 리눅스 샌드박스 + git 체크아웃뿐. `run_desktop.bat`은 Windows·`.venv32`·Kiwoom OCX·`.env` 시크릿을 요구한다. 셋 다 클라우드에 없다 | 메모리 `desktop-market-32bit`, `asset-portfolio-desktop-only`; `.env` gitignored | **critical** |
| A-2 | 실행이 불가능한데 "문제가 생길시 수정"까지 위임 → 에이전트는 **검증 못 하는 코드를 상상으로 고친다**. 최악의 조합(권한 있음 + 피드백 없음) | 프롬프트 4행 | **critical** |
| A-3 | 프롬프트는 "하루 2회(07/21시)"라고 쓰였으나 cron은 1회. 클라우드 루틴 최소 간격 1시간이라 2회는 루틴 2개가 필요 | cron `0 22 * * 0-4` | major |
| A-4 | 결과가 `claude/gracious-volta` 장수 브랜치에 누적. main은 하루 20커밋씩 전진 → 리베이스 충돌 확정, 병합 경로 없음 | outcomes.git_info | major |

판정: **구조적으로 성립 불가.** 프롬프트를 고쳐서 살릴 수 없고, **티어를 바꿔야** 한다(§3-7).

### 1-2. 「th_bot 전체 코드 점검」 `trig_01NFhDggq3joeaeDP9rUr6jQ`

```
cron  : 36 0 * * * (UTC) = 09:36 KST 매일
model : (미지정)
prompt: Review the entire TH_BOT codebase for functionality and efficiency.
        1. 의도대로 동작하지 않는 코드 식별·테스트·수정  2. 비효율 리팩터링
        3. 변경 후 재테스트  4. 변경 요약
outcome branch: claude/affectionate-thompson
```

| # | 문제 | 근거 | 등급 |
|---|---|---|---|
| B-1 | **무기억(stateless)** — 매 실행이 0에서 시작. 어제 뭘 고쳤는지, 뭘 시도했다 실패했는지 모른다. 적분항이 없으니 수렴하지 않는다 | 프롬프트에 상태 파일 참조 없음 | **critical** |
| B-2 | **무경계** — "entire codebase"는 1세션에 불가(모듈 수십 · 테스트 30). 매번 다른 곳을 훑는 랜덤 커버리지 | 프롬프트 1행 | **critical** |
| B-3 | **무기준** — "의도대로"의 의도가 어디에도 정의돼 있지 않다. design/20~25가 정본인데 프롬프트가 안 가리킨다 → 정상/이상 판정이 LLM 주관 | 프롬프트 | **critical** |
| B-4 | **무판정 게이트** — 수정이 통했는지 재측정하는 객관 기준 없음. "re-test"를 에이전트 자체 판단에 맡김 | 프롬프트 3행 | major |
| B-5 | 모델 미지정 → 실행마다 동작 등급이 달라질 수 있음 | session_context에 `model` 없음 | major |
| B-6 | A-4와 동일한 장수 브랜치 누적 문제. 게다가 이 저장소는 **GitHub Pages로 자동 발행**된다 — 미검증 리팩터링이 그대로 공개 사이트에 나갈 경로 | outcomes.git_info | major |
| B-7 | 리팩터링 권한 + 사람 게이트 없음 → 변경이 실익 대비 위험 초과 | 프롬프트 2행 | major |

판정: **의도는 맞고 구조가 틀렸다.** 이 루틴이 하려던 일을 §3의 루프로 재구성한다.

### 1-3. 공통 근본원인 (한 줄)

> 두 루틴 모두 **센서가 없다.** `runlog.json`·Actions 실행 이력·`docs/data/**` 신선도라는
> 실측 신호가 이미 생성되고 있는데, 프롬프트 어디도 그걸 읽지 않는다.
> 센서 없는 제어기는 정의상 개루프이고, 개루프에 수정 권한을 주면 드리프트한다.

---

## 2. 설계 원칙 (루프 엔지니어링 5조)

1. **판정은 코드가, 수정만 LLM이.** 정상/이상 판정을 LLM에 맡기면 매번 기준이 흔들린다. 판정은 결정론적 프로브(파이썬)가 하고, LLM은 이미 확정된 이슈 1건만 고친다.
2. **기억은 파일에.** 세션은 매번 죽는다. 루프의 적분항은 저장소 안의 append-only 원장(`ops/ledger.jsonl`)이다.
3. **게인은 작게 — WIP=1.** 1회 실행 = 최대 1이슈. 큰 게인(= "전체 점검")은 진동한다.
4. **탐색과 수렴을 분리.** 이슈를 *찾는* 루틴(Auditor, 코드 수정 금지)과 *고치는* 루틴(Fixer, 이슈 1건)은 다른 루틴이다. 한 세션이 둘 다 하면 찾은 걸 급히 고치고 검증을 건너뛴다.
5. **안티와인드업(재시도 상한).** 같은 이슈 2회 연속 검증 실패 → `escalated`로 잠그고 사람에게 알림. 이게 없으면 A-1 같은 불가능한 이슈에 매 실행을 태운다.

---

## 3. 목표 구조

```
    [기준] ops/slo.yml ─────────────┐
                                    ▼
 GH Actions ─┐              ┌──────────────┐   violations
 runlog.json ┼─(무료 계측)─▶│ health_probe │──────────┐
 docs/data/  │              │  (pure py)   │          │
 desktop_    ┘              └──────────────┘          ▼
 health.json                                   ops/health/latest.json
                                                      │
                        ┌─────────────────────────────┤
                        ▼                             ▼
                 ops/ledger.jsonl  ◀── 상태기계 ──▶  AI Office «Loop» 패널
                        │  (open/fixing/verifying/closed/escalated)
        ┌───────────────┴───────────────┐
        ▼ 주1회                          ▼ 일1회
   [Auditor 루틴]                   [Fixer 루틴]
   설계문서 대비 감사                open 이슈 상위 1건
   → 이슈 발행만                    → fix/<id> 브랜치 PR
   (코드 수정 금지)                       │
                                          ▼
                                  health.yml (검증 게이트)
                                  pytest + probe 재측정
                                  ├ 해당 위반 소거 확인
                                  └ 신규 위반 0 확인
                                          │
                                  green ─▶ 사람 머지 ─▶ closed
                                  red   ─▶ attempts+1 (2회 → escalated + push 알림)
```

### 3-1. 기준 — `ops/slo.yml` (신규)

워커·워크플로별 **설정점**을 기계가 읽는 형식으로 명문화. "정상"의 정의를 LLM 밖으로 뺀다.

```yaml
workers:                       # runlog.json 의 워커명 그대로
  "News Research":   {max_age: 90m,  status: [completed],          min_items: 50}
  "Stock KR Ranking":{max_age: 26h,  status: [completed],          min_items: 2000, market_hours_only: true}
  "Asset Kiwoom":    {max_age: 26h,  status: [completed, skipped], tier: desktop}
  "Vault Sync":      {max_age: 26h,  status: [completed, skipped]} # 토큰 없으면 skipped 정상
workflows:                     # .github/workflows/*.yml
  news:      {expect_every: 30m, max_consecutive_failures: 2}
  morning:   {expect_every: 24h, max_consecutive_failures: 1}
artifacts:                     # docs/data 산출물 신선도(design/21 4상태)
  "docs/data/macro/*.json": {max_age: 2h}
```

`max_age`는 design/21의 신선도 4상태(FRESH/DELAYED/STALE/CLOSED-SNAPSHOT)와 정합해야 하며,
`market_hours_only`·`tier` 같은 예외축은 **오탐을 없애기 위한 필수 항목**이다(장 마감 중 랭킹 미갱신은 정상).

### 3-2. 센서 — `scripts/health_probe.py` (신규, LLM 없음)

입력 4종을 읽어 위반 목록을 낸다. 결정론적이라 비용 0, CI 안에서 매 빌드 돌려도 무해하다.

| 입력 | 읽는 것 |
|---|---|
| `docs/ai-office/runlog.json` | 워커 20종 status/last_run/items/last_error |
| `gh run list --json` | 워크플로 6종 최근 N회 성공/실패/소요 |
| `docs/data/**/*.json` | Envelope 타임스탬프 → 신선도 |
| `data/cache/desktop_health.json` | 데스크톱 티어 원격 신호(§3-7) |

출력 `ops/health/latest.json`:

```json
{"probed_at":"...","violations":[
  {"id":"w.news-research.stale","severity":"major","subject":"News Research",
   "rule":"max_age 90m","observed":"last_run 4h12m ago","tier":"cloud","streak":3}
]}
```

`id`는 **규칙+대상의 안정 해시** — 같은 문제가 재발하면 같은 id여야 원장이 성립한다.

### 3-3. 적분항 — `ops/ledger.jsonl` (신규, append-only)

```jsonl
{"ts":"...","id":"w.news-research.stale","state":"open","first_seen":"..."}
{"ts":"...","id":"w.news-research.stale","state":"fixing","pr":"#41","attempt":1}
{"ts":"...","id":"w.news-research.stale","state":"closed","verified_by":"health.yml#992"}
```

상태기계: `open → fixing → verifying → closed`, 실패 시 `→ open(attempt+1)`,
`attempt≥2 → escalated`(자동수정 중단, 사람 대기), 사람이 판단하면 `wontfix`.
append-only라 봇 커밋이 30분마다 나는 main에서도 충돌이 거의 안 난다.

### 3-4. 제어기 A — 「Auditor」 루틴 (주1회, **코드 수정 금지**)

기존 「th_bot 전체 코드 점검」의 **의도를 승계**하되 경계를 준다.

- 스케줄: 일요일 21:00 KST(= `0 12 * * 0` UTC) — 주말 저지대, 봇 커밋 적음
- 범위: **주차 번호 mod N으로 1개 영역만.** 예: `[collectors, validators, repositories, calculators, generators, workflows+build, tests+docs]` 7영역 → 7주 1순환. 매주 다른 곳을 확실히 훑는다(현행의 랜덤 커버리지 해소, B-2)
- 기준: 프롬프트가 `design/20~25`를 정본으로 명시(B-3 해소). "비효율"이 아니라 **"설계문서 대비 불일치"**를 찾는다
- 산출: `ops/ledger.jsonl`에 이슈 append하는 PR **1개만.** `.py` 수정 diff가 있으면 CI가 PR을 거절(B-7 해소)
- 모델: `claude-opus-5` 고정(B-5 해소)

### 3-5. 제어기 B — 「Fixer」 루틴 (일1회, WIP=1)

- 스케줄: 08:00 KST = `0 23 * * *` UTC(전일 23:00) — morning 배치(06:30 KST)와 stock KR 개장 배치 이후, 사람이 결과를 아침에 확인 가능
- 절차(프롬프트에 고정): ① `ops/health/latest.json` + `ops/ledger.jsonl` 읽기 → ② `escalated/wontfix` 제외, severity·streak 순 **상위 1건** 선택 → ③ 그 이슈만 수정 → ④ 로컬 `pytest` + 관련 `build.py <target>` 통과 확인 → ⑤ `fix/<issue-id>` 브랜치로 PR, 원장에 `fixing` append → ⑥ **머지하지 않고 종료**
- 처리할 open 이슈가 없으면 **아무것도 안 하고 종료**(현행 B가 "할 일 없으면 만들어내는" 문제 차단)
- 모델: `claude-opus-5`

### 3-6. 구동·검증 — `.github/workflows/health.yml` (신규)

`on: [pull_request, schedule(매시), workflow_dispatch]`. **`concurrency: pages-commit`에 넣지 않는다**
(푸시하지 않으므로 빌드 대기열 뒤에 줄 설 이유가 없다).

- schedule 실행: probe만 돌려 `ops/health/latest.json` 갱신 → 위반 있으면 커밋
- pull_request 실행(= 검증 게이트): `pytest` → 대상 타깃 빌드 → probe 재측정 →
  **(가) PR이 주장하는 위반 id가 사라졌는가 (나) 신규 위반이 0인가.** 둘 다 참일 때만 green(B-4 해소)
- green이어도 **머지는 사람이** — 최소 도입 후 4주. 이후 성공률(§5) 보고 auto-merge 검토

### 3-7. 데스크톱 티어 — A-1/A-2의 해법

클라우드가 못 하는 일을 클라우드에 시키지 않는다. 역할을 쪼갠다.

| 티어 | 실행 주체 | 담당 | 권한 |
|---|---|---|---|
| Cloud | 루틴(Auditor/Fixer) | 코드·CI·데이터 계약 | PR 생성 |
| Desktop | **로컬 예약작업**(Windows 작업 스케줄러, 기존 `scripts/register_schedule.ps1` 확장) | `run_desktop_auto.bat` 실행, Kiwoom/자산/야간선물 | 실제 실행 + 커밋 |

데스크톱 작업은 실행 후 `data/cache/desktop_health.json`(성공여부·계좌별 수집 건수·에러 메시지,
**금액 평문 금지** — 기존 `guard-plaintext` 대상)을 써서 push한다.
클라우드 루프는 그 파일을 **원격 센서**로 읽어 `tier: desktop` 위반을 감지하고,
직접 고치는 대신 **이슈 발행 + 사람 알림**만 한다. "실행했다"고 주장할 수 없는 구조가 된다.

→ 기존 「run_bat 점검」 루틴은 **삭제**(claude.ai/code/routines에서 사용자가 직접 — API로 삭제 불가)
하고, 그 기능은 로컬 예약작업 + desktop_health 센서로 이관한다.

### 3-8. 사람 인터페이스

- `docs/ai-office/index.html`에 **Loop 패널** 추가: open/fixing/escalated 이슈, streak, 최근 처리 이력. AI Office가 이미 runlog를 렌더링하므로 데이터원만 추가하면 된다
- `escalated` 발생 시 push 알림(두 루틴 모두 `notifications.push: true` 이미 설정됨)

---

## 4. Phase 계획 (각각 독립 배포 가능)

| Phase | 내용 | 산출 | LLM 의존 | DoD |
|---|---|---|---|---|
| **A** ✅ | `config/slo.py` + `scripts/health_probe.py` (§8) | 위반 목록 JSON | 없음 | 현행 저장소에 프로브 실행 → 위반 목록이 **사람 눈으로 봐도 맞다**(오탐 0 확인). 테스트 `tests/test_health_probe.py` |
| **B** ✅ | `health.yml`(schedule 모드만) + AI Office Loop 패널 | 시간별 자동 갱신되는 건강 대시보드 | 없음 | 1주 무인 운전 후 오탐 없음. **이 시점에서 루틴 없이도 이미 이득** |
| **C** | 데스크톱 티어: 로컬 예약작업 + `desktop_health.json` + **기존 「run_bat 점검」 루틴 폐기** | 실행 가능한 데스크톱 자동화 | 없음 | 데스크톱 미실행 24h → 프로브가 major 위반으로 검출 |
| **D** | `ops/ledger.jsonl` 상태기계 + `health.yml` PR 검증 모드 | 검증 게이트 | 없음 | 일부러 만든 회귀 PR이 red, 정상 PR이 green |
| **E** | **Fixer 루틴** 등록(기존 「th_bot 전체 코드 점검」을 이 프롬프트로 교체) | 일1회 자동 PR | 있음 | 4주간 PR 전량 사람 리뷰. 자동수정 성공률 측정 |
| **F** | **Auditor 루틴** 등록(영역 로테이션) | 주1회 이슈 발행 | 있음 | 발행 이슈의 유효율 ≥ 70% |
| **G** | 튜닝 — 임계값·에스컬레이션 정책·auto-merge 여부 | — | — | §5 지표 기준 충족 |

**A~D는 LLM이 전혀 없어도 성립한다.** 루프의 신뢰성은 여기서 나오고, E·F는 그 위에 얹는 자동화일 뿐이다.
순서를 뒤집어 루틴부터 손대면 지금과 같은 개루프가 반복된다.

---

## 5. 루프 자체의 계측 (메타 루프)

자동수정 시스템도 측정 대상이다. `ops/ledger.jsonl`에서 자동 산출한다.

| 지표 | 정의 | 목표 | 미달 시 조치 |
|---|---|---|---|
| MTTR | `open → closed` 중앙값 | ≤ 48h | Fixer 빈도 상향 |
| 자동수정 성공률 | `closed(자동)` ÷ `fixing` 시도 | ≥ 60% | **권한 축소** — Fixer를 이슈 발행 전용으로 강등 |
| 오탐률 | `wontfix` ÷ 전체 발행 | ≤ 15% | `slo.yml` 임계값 재조정 |
| 에스컬레이션 | 주당 `escalated` 건수 | ≤ 2 | 근본원인 사람이 직접 처리 |

성공률이 2주 연속 50% 미만이면 **자동수정을 끄고 감지·알림만 유지한다.** 이 후퇴 경로가 설계에 포함돼 있어야
"자동화가 상황을 악화시키는" 실패모드를 막을 수 있다.

---

## 6. 하지 않는 것

- **auto-merge 초기 도입** — 최소 4주 사람 머지. GitHub Pages 자동 발행 저장소에서 미검증 자동 머지는 사고 경로다(B-6)
- **장수 `claude/*` 브랜치 유지** — 이슈 1건 = 단명 PR 1개. 하루 20커밋 나는 main에서 장수 브랜치는 리베이스 지옥
- **클라우드에서 Kiwoom/자산 실행 시도** — 물리적으로 불가(A-1). 원격 센서로만 관측
- **LLM에 정상/이상 판정 위임** — 판정은 `slo.yml` + probe
- **루틴 간격 1시간 미만** — 클라우드 루틴 최소 간격 제약. 더 촘촘한 감지는 `health.yml` schedule(무료)로
- **design/25 선행 요구** — 본 루프는 25(공급망 이관)와 독립. 다만 25 구현 시 프로브의 캐시 경로 항목은 함께 갱신

---

## 7. 결정 사항 (2026-07-29 확정 — 구현은 이 표를 따른다)

| # | 결정 사항 | 확정 |
|---|---|---|
| D-1 | 기존 「run_bat 점검」 루틴 | **삭제 완료**(사용자 직접). 기능은 Phase C의 로컬 예약작업 + desktop_health 센서로 이관 |
| D-2 | 기존 「th_bot 전체 코드 점검」 루틴 | **삭제 완료**. Phase E에서 Fixer 프롬프트로 **새로 등록**한다(재사용할 루틴이 없음) |
| D-3 | Auditor 영역 분할 수 | 7영역/7주 순환 |
| D-4 | Fixer WIP | 1 (고정) |
| D-5 | 착수 범위 | **Phase A~B** — 완료(§8) |

확정 시점 기준 등록된 클라우드 루틴은 **0개**다. 루프가 자동으로 코드를 고치는 경로는 현재 없고,
Phase E·F에서 새 루틴을 등록할 때 비로소 생긴다.

---

## 8. Phase A~B 구현 기록 (2026-07-29 완료)

설계 대비 바뀐 점과 그 이유. 나머지는 §3 그대로다.

| 설계(초안) | 구현 | 이유 |
|---|---|---|
| `ops/slo.yml` | **`config/slo.py`** | `config/themes.py`·`config/economic_calendar.py`가 이미 "주석 달린 파이썬 상수 테이블"이라는 이 저장소의 설정 관례다. 이 한 파일 때문에 PyYAML을 requirements에 넣을 이유가 없다 |
| 입력 축 4종 | **3종**(runlog · gh 워크플로 · 미구현 desktop_health) | 산출물(`docs/data/**`) 신선도 축을 뺐다 — CI 체크아웃에서 파일 mtime은 체크아웃 시각이라 무의미하고, 발행 JSON에 공통 타임스탬프 규약이 없다(`rankings.json`엔 as_of가 있고 `ta/preview.json`엔 없다). 부정확한 축으로 오탐을 만드느니 뺀다. Phase D에서 재검토 |
| `ops/health/YYYY-MM-DD.json` 일자 사본 | **`latest.json` 단일** | 일자 사본은 연 365개 커밋 파일로 쌓인다. 이력은 Phase D의 원장(`ops/ledger.jsonl`)이 담당하므로 중복이다 |
| health.yml은 `pages-commit` 그룹에서 **제외** | **포함** | 초안의 근거는 "푸시하지 않으므로"였는데, 실제 구현은 `ops/`를 커밋한다. 같은 브랜치에 쓰는 이상 직렬화가 푸시 경합보다 안전하다 |
| health.yml에 PR 검증 모드 | **schedule + dispatch만** | PR 게이트는 원장 상태기계가 있어야 성립한다(Phase D) |

### 8-1. 산출물

| 파일 | 역할 |
|---|---|
| `config/slo.py` | 워커 21종 + 워크플로 6종의 설정점. "정상"의 단일 정의 |
| `scripts/health_probe.py` | 센서. `--check`(exit 1) / `--json` / `--no-gh` |
| `.github/workflows/health.yml` | 매시 15분 프로브 → `ops/health/latest.json` 커밋 |
| `tests/test_health_probe.py` | 규칙별 정탐 + **건강한 runlog에서 위반 0** 검증(39 케이스) |
| AI Office `Loop` 패널 | `docs/ai-office/` 최상단. 센서 기록이 없으면 "위반 없음"이 아니라 **"센서 기록 없음"**으로 표시 |

### 8-2. 센서가 첫 실행에서 찾아낸 것

**① runlog 공유 원장의 기록 유실 (수정 완료)**

`docs/ai-office/runlog.json`은 CI(워크플로 6종)와 데스크톱이 같이 쓰는 누적 원장인데,
`app/deploy.py`의 rebase가 `-X theirs`로 **데스크톱 사본을 채택**한다. 생성물은 재빌드로 정정되지만
runlog는 재빌드로 복원되지 않는 누적 원장이라, 데스크톱이 돌리지 않는 워커의 기록이 통째로 사라진다.

실제 사고 — `d2ea8e5 chore(desktop): sync 2026-07-28 07:49`가 `6c831a3 chore(financials)`가 기록한
`FS DART corpCode`·`FS EDGAR CIK맵`을 삭제했다. 센서는 이걸 `w.fs-*.missing` 위반으로 검출했다.

수정: `utils/runlog.merge_by_recency()` 신설 + `app/deploy._restore_remote_runlog()`가 rebase 직후
원격 사본을 워커별 `last_run` 최신 기준으로 병합한다. 단순 `{**remote, **local}`이 아니라 **시각 비교**인
이유는, 데스크톱 로컬 사본의 낡은 기록이 원격 최신 기록을 덮으면 이번엔 **가짜 stale 위반**이 생기기 때문이다.

**② `freshness_meta`의 기대주기 오표기 (수정 완료)**

`Theme Analyst`가 30분 주기로 표기돼 있었으나 실제로는 morning 타깃 전용(일1회)이다.
사본 테이블을 없애고 `config/slo.py`를 직접 읽게 했다 — 기대주기의 단일 기준을 하나로 만든다.

### 8-3. Phase A DoD("오탐 0") 검증 과정에서 정정한 SLO

초안 작성 시 `Data Officer`를 morning 전용(일1회)으로 잡았으나, 실측 결과 `generators/dashboard_v2`가
`pipelines.get_market()`을 호출하고 **대시보드는 build.py 공통 마무리라 모든 타깃이 지나간다** —
실효 주기는 30분(news.yml)이다. 30분→일1회로 잘못 잡았다면 하루짜리 장애를 놓쳤을 값이다.
SLO 값은 크론만 보고 정하면 틀린다는 사례로 남긴다.

### 8-5. 감사 기준·원장·vault 축적 (2026-07-30 추가)

Phase D(원장)의 **데이터 계층을 앞당겨** 구현했다. 이유는 두 가지다 — ① 이번 세션에서 이미
실제 결함 3건을 찾았는데 담아 둘 곳이 없었고, ② 이슈를 Obsidian에서 조회·복기하려면 원장이
선행돼야 한다. 상태기계와 검증 게이트(Phase D의 나머지)는 그대로 남아 있다.

| 파일 | 역할 |
|---|---|
| `config/audit_rubric.py` | **코드 품질**의 판정 기준. P01~P20 우선순위 + 도메인 점검 18종 + SOLID/DRY/KISS/YAGNI + 안전 규칙 6조 + 7영역 로테이션. `config/slo.py`가 런타임 상태 기준이라면 이쪽은 코드 기준이다 |
| `utils/ledger.py` | append-only JSONL 원장 + 상태기계 + WIP=1 대상 선택 + 안티와인드업 |
| `generators/vault_ops.py` | 원장 → `TH_DATA/50_Ops/loop/*.md` 투영(멱등). Dataview INDEX 포함 |
| `ops/prompts/{auditor,fixer}.md` | 루틴이 읽는 **버전관리되는 프롬프트** |

**루틴 프롬프트를 저장소에 둔 이유.** 클라우드 루틴에 프롬프트를 인라인으로 박으면, 기준을
바꿀 때마다 루틴을 편집해야 하고 변경 이력이 남지 않는다. 루틴에는 "저장소를 clone하고
`ops/prompts/auditor.md`를 읽어 따르라" 한 줄만 넣는다. 기준은 코드와 함께 리뷰되고 함께 롤백된다.

**vault 쓰기 위치는 `50_Ops/`다** — `10_Journal/`이 아니다. TH_DATA는 "Trading 장기기억
저장소"이고, 그 폴더의 Dataview 조회축(trade-journal/morning-report/news-digest)에 엔지니어링
이슈가 섞이면 매매 복기 쿼리가 오염된다. 쓰기 주체 규칙(봇만)은 동일하며 TH_DATA/README.md에
`loop-issue` 스키마 행을 추가했다.

**보고 형식이 곧 스키마다.** `REPORT_FIELDS = (문제점, 원인, 해결방법, 성능향상, 부작용)`을
`record()`가 강제하므로 "문제점만 있고 해결방법이 없는 지적"이 원장에 들어갈 수 없다.

### 8-6. 원장 시드 (2026-07-30, 실측 근거만)

| id | 상태 | 우선순위 | 내용 |
|---|---|---|---|
| `h.build-ci.runlog-overwrite` | closed | P19 | runlog 공유 원장 유실 (§8-2 ①) |
| `h.generators.freshness-expected-dup` | closed | P01 | 기대주기 사본 테이블 오표기 (§8-2 ②) |
| `h.utils.ledger-default-leak` | closed | P19 | `record()` 기본값이 전이 이벤트에 새어 critical→major 변조 |
| `a.collectors.http-no-session-retry` | **open** | P11 | 컬렉터 HTTP 15곳에 Session·재시도·타임아웃 정책 없음 |
| `w.fs-workers.missing` | **open** | — | FS 워커 2종 기록 없음(프로브 검출, 원인 수정됨·재확인 대기) |

`h.utils.ledger-default-leak`은 원장을 만들다 원장이 잡은 결함이다. 상태 전이 이벤트가
시그니처 기본값을 함께 실어 최초 severity를 덮었다 — 부분 갱신을 설계 의도로 잡아 놓고
"명시하지 않음"과 "기본값"을 구분하지 못하게 만든 전형적 실수다.

### 8-7. 다음 단계 진입 조건

Phase C로 넘어가기 전에 **health.yml 1주 무인 운전 후 오탐 0**을 확인한다(§4 Phase B DoD).
현재 미확인 항목: gh 축(`gh run list`)은 로컬에서 검증할 수 없어 첫 CI 실행에서 확인해야 한다.
