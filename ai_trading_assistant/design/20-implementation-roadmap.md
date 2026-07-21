# 20. 구현 로드맵 (단계별 계획)

## 0. 이 문서의 위치와 읽는 법

이 문서는 신규 10페이지 체제로의 이행을 **단계(Phase)** 단위로 지휘하는 최상위 계획서다. 3부작 중 첫 문서이며, 나머지 둘과 역할을 분담한다.

- **20 로드맵(본 문서, 지침 A)** — 무엇을 어떤 순서로, 무엇이 끝나면 다음으로 넘어가는가.
- **21 데이터 요구 명세(지침 B)** — Envelope 전 필드 정의·JSON Schema·소스별 신선도 실측표·결측 강등 문법·암호화 파라미터.
- **22 아키텍처(지침 C)** — `base_v2` 블록체계·`config/nav.py` 계약·토큰 스코프·`build.py` 레지스트리 디스패치·`freshness.js` 계약·발행채널·워크플로 구성.

각 Phase의 완료 기준은 본 문서만으로 검증 가능하도록 명세하되, **필드 정의·스키마·토큰 값·JS 모듈 계약의 상세**는 21·22를 참조한다(중복 서술 금지). 페이지별 UX 스펙은 `00~10` 문서가 단일 진실 소스다.

**골격 원칙(심사 확정):** `얇은 수평 기반 → 수직 슬라이스 파일럿 → 라이브 페이지 먼저 → 최중량 데이터 나중`. 데이터 계약을 Phase 0에서 못 박아 이 프로젝트의 진짜 병목(무료 소스 공백·Kiwoom 수동·소급 불가 히스토리·야간선물 신선도 사고)을 전진 배치하고, Phase 2 TA 수직 슬라이스로 계약의 쓸모를 형식검증이 아닌 실화면으로 조기 검증한다. **기존 URL·아카이브 전수 보존, `base.html` 소스 동결(Phase 9까지).**

### 0-1. 전 Phase 공통 전제 (정본 선언 — 교차 문서 상충 해소 결과)

교차 리뷰에서 발견된 문서 간 상충을 아래와 같이 단일 진실로 확정한다. 본 로드맵의 모든 Phase 서술·DoD는 이 정본을 따른다.

1. **신선도 상태 모델 = 4상태** — `FRESH / DELAYED / STALE / CLOSED-SNAPSHOT`(문턱 T·3T)을 정의한 **00 디자인 시스템이 정본**이다. 데이터군별 T·STALE 문턱의 실측값은 21 실측표를 따르며, 21에 DELAYED 열이 추가되어 무명 구간(T~3T)이 소거된다. 본 문서의 Phase 0 일반화·Phase 1 토큰·Phase 2 DoD는 전부 4상태 기준으로 기술한다.
2. **계좌 구성 = 정확히 4종** — ① **키움증권**(단타·스윙 매매 주력) ② **한국투자 위탁**(미국주식 전용 — USD/KRW 듀얼 표시·적용환율 필수) ③ **한국투자 ISA**(ETF 전용·절세) ④ **BYBIT**(암호화폐). KB증권은 사용자 결정으로 삭제되었고, 수기 입력 경로도 함께 사라져 **자산 파이프라인은 전량 자동 수집**(키움 TR 로컬 + KIS REST + Bybit REST)이며 자산 신선도는 **T=24h 단일 규칙**이다(수기 7일 규칙 없음). 08·09 문서는 이미 4계좌 기준 개정 완료.
3. **자산 평문 스냅샷 원장 = 로컬 전용** — `data/snapshots/`는 **`.gitignore` 등재·커밋 금지**가 단일 진실이다(21 §9-4 정본). 발행물은 `assets.enc.json` 암호문 단독이며, 90일 히스토리는 암호문 payload 내부에 담는다. 공개 리포에 평문 원장이 한 번이라도 커밋되면 git 히스토리에서 삭제 불가하므로, pre-commit·CI 이중 가드로 경로 유입 자체를 차단한다(Phase 8).
4. **아카이브 = 동결 자산** — 기존 발행 HTML(`docs/morning/YYYY-MM-DD/` 등)은 재생성하지 않는 동결 산출물이며, 이들이 하드코딩 참조하는 `docs/static/css/style.css`(실측: `href="../../static/css/style.css"`)는 **아카이브 전용 동결 자산으로 영구 배포 유지**한다. Phase 9의 v1 셸 은퇴는 **소스(templates/·static/ 소스본) 한정**이다.

---

## 1. 전체 단계 개요표 (Phase 0~9)

| Phase | 이름 | 목표(한 줄) | 핵심 산출물 | 완료 기준(한 줄) |
|---|---|---|---|---|
| 0 | 데이터 계약 표준 | 전 페이지 공유 JSON 봉투 + 신선도(4상태)/세션 판정 계약 확정 | `envelope.schema.json` + 컨테이너 `market.schema.json`, 확장 `Quote`, 일반화 validator | market.json 컨테이너 스키마 통과 · 잔존 전 항목 `as_of_iso·session` non-null · 야간선물 테스트 일반화 규칙 위에서 통과 |
| 1 | 공존 셸 + 토큰 최소본 | 신·구 셸 공존 골격 + 다크 우선 토큰 + 데이터주도 nav | `base_v2.html`, `config/nav.py`, `tokens.css`(등락 글로벌 값 포함) | 고정 조건 재빌드 정규화 diff 0 · v2 스켈레톤 렌더 · v2 신규 파일 hex 0건 · pytest 그린 |
| 2 | TA 수직 슬라이스 파일럿 | 계약+셸+토큰+클라판정을 최저비용 신규페이지로 관통 실증 | `docs/ta/`, `preview.json`, `freshness.js`(`?now=` 훅), `meta/freshness.json` | v2 셸 렌더 · `?now=` 주입으로 DELAYED·STALE 강등 재현 · 신선도 pytest 통과 |
| 3 | 시세 유니버스 증분 확장 | 신규 수집기 없이 심볼만 추가해 계약을 20+지표로 실증 | 확장 `market.json`(MOVE·NatGas 포함), 스파크라인 JSON | 신규심볼 전량 스키마통과 · 실패심볼 None 강등 · `change_abs` 표기 |
| 4 | Dashboard(`/`) 치환 | 최다트래픽 랜딩 v2 치환(URL 불변) + 자산 평문 선차단 | 신규 `docs/index.html`, `updown.js` | `/` v2 렌더 · 자산 절대값 grep 0건 · Hero 결측 시 팩트우선 생략 |
| 5 | News(`/news/`) 치환 | 기존 URL 유지 4탭·펼침·키워드 레이더 + 날짜 아카이브 | 신규 `docs/news/index.html` + 아카이브, `tabs.js` | v2 렌더 · 탭 배타성 · 400건 회귀0 · L3 일상한 · 하위호환 테스트 통과 |
| 6 | Macroeconomics(`/macro/`) | 유니버스 무의존 독립 트랙(FRED·ECOS·Upbit) | `docs/macro/`, `indicators.json`, `calendar.json` | 확보지표 렌더 · 예상치 미입력 칸 생략 · STALE 강등 정상 |
| 7 | Stock + Hub + Financials + 글로벌 검색 | 최중량 데이터 그룹 + 전역 커맨드 팔레트(화면 현대화 후 착수) | `docs/stock/`, `docs/financials/`, 종목별 JSON, `search.js` | TOP30×2 렌더(모집단 캡션) · Hub 딥링크·포커스트랩 · Ctrl+K 팔레트→Hub 오픈 · FS 5년 카드 |
| 8 | Asset + Portfolio + `/trades` v2 | 개인자산 평문공개 사고를 코드 이전에 차단(A+D 암호화) + 매매일지 공개 v2 치환 | `docs/asset/`, `docs/portfolio/`, `assets.enc.json`, 신규 `docs/trades/` | 게이트 밖 자산 절대값 grep 0건 · 복호화=열람 · pre-commit+CI 이중 가드 동작 · 4계좌 스냅샷 자동 수집 |
| 9 | Settings + v1 셸 은퇴 | 마지막 v2 페이지 + 이중유지보수 종료(소스 한정 은퇴) | `docs/settings/`, v1 셸 **소스** 제거(동결 자산 유지) | templates/·generators/ v1 셸 참조 0건 · 소스 범위 단일 토큰시스템 · dated URL 전수 200 + 아카이브 스타일 정상 렌더 |

> Phase 0∥1(상호 무의존, 병렬 가능), Phase 6∥7(독립 트랙, 병렬 가능). 상세는 §2.

---

## 2. 단계 간 의존 관계도 (텍스트)

```
[결정, 비코드]                        암호화 정책(A+D)·KDF 파라미터 → Phase 4에서 착수/확정
                                       git add 대상 확장(docs + data/history) → Phase 7 전 결정
                                       /trades(trades.json) 공개 범위 → Phase 8 전 결정

Phase 0 (데이터 계약) ──┬────────────────→ Phase 3 (유니버스) ──┐
        │               │                                        ├─→ Phase 7 (Stock/Hub/FS/검색)
        │  (0 ∥ 1 병렬)  │                                        │
Phase 1 (공존 셸) ──────┴─→ Phase 2 (TA 파일럿) ─┬─→ Phase 4 ────┘
        │                                         └─→ Phase 5 (News)
        └──────────────────────────────────────────→ Phase 7 (panel_slot 제공)

Phase 0 ─────────────────→ Phase 6 (Macro, 독립 트랙)      (6 ∥ 7 병렬)

Phase 0 ─────────────────→ Phase 8 (Asset/Portfolio/Trades)   ※ v2 셸·freshness.js는 1·2 전제

Phase 2·3·4·5·6·7·8 ─(전부 완료)─→ Phase 9 (Settings + v1 은퇴)
```

**병렬 가능 구간(자원이 허락하면 동시 진행):**
- **0 ∥ 1** — Phase 0은 데이터 계층(계약·validator·repository), Phase 1은 프레젠테이션 계층(셸·토큰·nav)이라 접점이 없다. Phase 2가 둘을 처음으로 합류시키는 관문이다.
- **6 ∥ 7** — Macro는 시세 유니버스에 의존하지 않는 별도 파이프라인(FRED/ECOS/Upbit), Stock/FS는 별도 파이프라인(KRX/DART/EDGAR)이라 서로 독립. 1인 운영 현실상 동시 착수보다 순차가 안전하나 의존 관계상 병렬이 허용된다.

**비코드 선행 결정(구현 아님, 문서상 확정만):**
- **암호화 발행 정책 A+D 확정** — Phase 4에서 착수(대시보드 평문 선차단과 함께), Phase 8 구현의 선행. 상세 파라미터는 21 참조.
- **`git add` 확장 결정** — 소급 불가 히스토리 중 커밋 대상은 **전일 순위·PER/PBR 밴드로 한정**하며, Phase 7 착수 전 확정. **자산 스냅샷은 커밋 후보가 아니다**(§0-1 정본 3: 로컬 전용·`.gitignore`). 상세는 22 발행채널.
- **`/trades` 공개 범위 확정** — 매매일지는 공개 v2 페이지로 유지한다(§4). 단, `trades.json`의 개별 매매 손익 절대값 노출 여부는 Phase 8 착수 전 확정하고, 그 결정에 따라 Phase 8 DoD 1의 grep 패턴 범위(자산 총액·잔고 계열 한정 vs 매매 단위 포함)를 고정한다.

**전역 클라이언트 모듈 → 최초 구현 Phase 매핑(렌즈: 모든 전역 컴포넌트는 담당 Phase가 있어야 한다):**

| 모듈(계약 상세는 22 §5) | 역할 | 최초 구현 Phase | 비고 |
|---|---|---|---|
| 인라인 부트 스니펫 | 테마·등락 모드 FOUC 방지(저장값 조기 적용) | 1 | `base_v2.html` head 내 |
| `store.js` | localStorage/sessionStorage 단일 래퍼 | 1 | 부트 스니펫·Settings가 소비 |
| `freshness.js` | 열람시점 신선도 판정·배지(4상태) + `?now=` 시계 주입 훅 | 2 | 전 v2 페이지 공용 |
| `updown.js` | `[data-updown]` 등락색 모드 적용(한국/글로벌) | 4 | 값은 Phase 1 토큰에 선탑재, 토글 UI는 Phase 9 |
| `tabs.js` | 배타 탭 전환 | 5 | News 4탭이 최초 소비, FS·Hub 재사용 |
| `search.js` | Ctrl/⌘+K 커맨드 팔레트(그룹 3종·키보드 탐색) | 7 | `search-index.json`과 동시 |
| Hub 패널 로더 | `panel_slot` fetch·해시 라우팅·포커스 트랩 | 7 | Phase 1의 `panel_slot` 블록 위에서 |

---

## 3. 각 Phase 상세

각 Phase는 `목표 / 작업(체크리스트) / 산출물 / 완료 기준(DoD) / 검증 방법 / 리스크·롤백 / 선행 조건` 순서로 기술한다. DoD는 전부 grep·pytest·스키마검증 등 눈으로 확인 가능한 문장이다.

### Phase 0 — 데이터 계약 표준 (Envelope · 신선도/세션 · 발행채널)

- **목표:** 전 페이지 공유 JSON 봉투 규격과 열람시점 신선도·세션 판정 계약을 확정한다. 야간선물 3중 방어(e396e5b)를 페이지별 복제 없이 공통 계층으로 승격한다.
- **작업:**
  - [ ] Envelope 스키마 정의: `{value, change_abs, change_pct, unit, as_of_iso(UTC), source, session_key, expected_T_min, freshness_basis}` (전 필드 정의·JSON Schema는 21)
  - [ ] **컨테이너 스키마 `market.schema.json` 정의** — 실측상 `cache/market.json`의 최상위는 `{as_of: 문자열, 심볼 키: 객체|null}` 형태의 심볼 맵이므로, 항목 단위 `envelope.schema.json`만으로는 파일 전체를 검증할 수 없다. 최상위 메타 필드 + patternProperties로 항목마다 envelope `$ref`를 거는 컨테이너 스키마를 21 §1-2에 정의하고 검증은 이것을 기준으로 한다
  - [ ] `Quote`에 `as_of_iso·session·change_abs` 추가 — `from_dict` 하위호환(`.get` 기본값) 유지
  - [ ] validators `_fresh()`를 `_night` 전용에서 소스별 파라미터 규칙으로 일반화 — 상태는 **4상태 정본(FRESH/DELAYED/STALE/CLOSED-SNAPSHOT, §0-1)** 기준
  - [ ] `market_repository.persist`가 항목별 `as_of_iso·session`을 버리지 않도록 개정
  - [ ] `config/calendar.py` 세션·휴장 달력 신설(규격은 21)
  - [ ] 발행채널 정책 명문화: fetch 대상=`docs/data/**`, 소급불가 히스토리=`data/**`(단, 자산 스냅샷 제외 — §0-1 정본 3) (22 발행채널)
- **산출물:** `envelope.schema.json`, `market.schema.json`(컨테이너), 신선도·세션 규칙 명세, 발행채널 정책 문서, Quote 확장 필드표.
- **완료 기준(DoD):**
  1. `market.json`이 **컨테이너 스키마 `market.schema.json` 검증을 통과**한다(0 오류). 항목 단위 검증은 컨테이너의 `$ref`를 통해 `envelope.schema.json`으로 위임된다.
  2. 검증된 `market.json`에서 **None 강등으로 제거되지 않고 남은 전 항목이 `as_of_iso·session` non-null**이다.
  3. 기존 야간선물 60h 만료·flat 차단 테스트(`test_validators.py`)가 **일반화된 `_fresh()` 위에서 수정 없이 그대로 통과**한다.
- **검증 방법:** `python -m jsonschema -i cache/market.json market.schema.json` → 0 exit(또는 항목별 순회 검증 스크립트로 심볼당 envelope 검증 전건 통과). `pytest tests/test_validators.py -q` → green. `python -c` 로 market.json 로드 후 잔존 항목의 `as_of_iso`/`session` None 개수 카운트 = 0.
- **리스크·롤백:** `Quote` 필드 추가가 기존 캐시 역직렬화를 깰 위험 → `from_dict` 기본값으로 하위호환 보장, 실패 시 필드 추가분만 revert(모델 1파일). validator 일반화가 야간선물 방어를 약화시킬 위험 → 야간선물 테스트를 회귀 게이트로 고정, 실패 시 `_fresh()` 일반화를 보류하고 `_night` 전용 규칙을 파라미터화 이전 상태로 되돌린다.
- **선행 조건:** 없음(최우선).

### Phase 1 — 공존 셸 + 토큰 최소본 (사용자 화면 무변화)

- **목표:** 신·구 셸을 공존시키는 strangler-fig 골격 + 다크 우선 토큰 레이어 + 데이터주도 nav를 세운다. **사용자에게 보이는 화면은 변하지 않는다.**
- **작업:**
  - [ ] `base_v2.html` 신설(사이드바 240 + 헤더 64, 블록 `head_extra·scripts·panel_slot`) — **`base.html`은 한 줄도 건드리지 않는다**
  - [ ] `config/nav.py` 단일 소스 신설(두 셸이 공유; 계약은 22)
  - [ ] `tokens.css` 신설(원시 팔레트→시맨틱, 신선도 상태색은 **4상태 정본** 기준 — FRESH 무배지/DELAYED/STALE 배지색 + CLOSED-SNAPSHOT 라벨, 값은 00·21). 등락색 `data-updown` 스코프는 **한국·글로벌 두 값 모두 Phase 1에서 채운다**(Settings ① 토글의 동작 전제). **라이트 테마만 스위칭 슬롯 예약 후 값 채움 유예**
  - [ ] `store.js` + 인라인 부트 스니펫(FOUC 방지 — 저장된 테마·등락 모드 조기 적용)
  - [ ] `build.py`를 레지스트리형 디스패치로 재설계(기존 5타깃 `TARGETS` 회귀 0)
- **산출물:** `base_v2.html`, nav 컨텍스트, `tokens.css`, `store.js`, nav 미노출 v2 스켈레톤 라우트 1개.
- **완료 기준(DoD):**
  1. **고정 조건 재생성 정규화 diff 0** — 레지스트리 재설계 전·후 커밋 각각에서 아래 고정 조건으로 `python build.py all`을 실행한 v1 6페이지 산출물의 **정규화 diff가 0**이다. 고정 조건: (a) `cache/` 입력 데이터 동결(빌드 간 수집 결과 고정), (b) Notion sync 비활성 — `NOTION_API_KEY` 미설정 시 skipped 처리되는 현행 경로 사용(실측: `build.py` `_sync_notion()`이 `notion_collector.enabled()` false면 skip), (c) `generated_at` 고정 — 환경변수/파라미터로 빌드 시각을 고정 주입하거나, 정규화 diff에서 타임스탬프 렌더 라인(실측: `dashboard.html`의 '최종 갱신 {{ generated_at }}' 등 5개 템플릿) 제외를 허용한다. ※ 무조건적 "바이트 동일"은 현행 코드상 달성 불가(타임스탬프·Notion 변동)이므로 채택하지 않는다.
  2. v2 스켈레톤 라우트가 정상 렌더된다.
  3. **v2 신규 파일 한정** hex 스캔 0건 — `tokens.css`(원시 팔레트 정의부 제외)·`base_v2.html`·v2 신규 CSS(`base_v2.css`·`components.css` 등 22의 파일 목록 기준)·v2 템플릿에서 `grep -rEn '#[0-9a-fA-F]{3,6}'` 결과 0건. ※ v1 `style.css`는 하드코딩 hex를 가진 채 Phase 9까지 동결이고 `docs/`에는 그 사본·기존 발행 HTML이 남으므로, 경로 무제한 전역 grep은 게이트로 성립하지 않는다. 소스 범위 hex 0건은 Phase 9 DoD로 이관.
  4. `pytest` 전체 green, 신규 페이지 가로 스크롤 0.
- **검증 방법:** 고정 조건 명시 후 2회 빌드 → 정규화 diff 스크립트 0 확인(`git diff --stat docs/` 병용). hex grep을 **대상 경로를 명시해** 실행(v2 신규 파일 목록). `pytest -q`.
- **리스크·롤백:** `build.py` 레지스트리 재설계가 기존 타깃 분기를 깰 위험 → v1 6페이지 정규화 diff 0이 회귀 게이트. 실패 시 레지스트리 도입을 보류하고 기존 if-분기에 v2 타깃만 추가하는 최소 변경으로 후퇴. `base_v2`는 별도 템플릿이므로 롤백 시 삭제만으로 무영향.
- **선행 조건:** 없음(Phase 0과 병렬 가능).

### Phase 2 — 수직 슬라이스 파일럿: TA end-to-end (검증 관문)

- **목표:** 계약+셸+토큰+클라이언트 판정을 **최저비용 신규 페이지**로 관통 실증한다(라이브 무간섭). 제안3의 "UI 최후" 약점을 상쇄하는 결정적 관문이다.
- **작업:**
  - [ ] KOSPI `^KS11` 일봉 60일+ 수집 + RSI(14)/이평/이격/추세 calculator(순수 계산)
  - [ ] `docs/data/ta/preview.json`(봉투 규격) 발행
  - [ ] `static/js/freshness.js` 단일 모듈 신설(열람시점 시계 × `as_of` × 세션 → 4상태 배지). **테스트용 시계 주입 훅 1개(`?now=` 쿼리 파라미터) 포함** — 내부에서 `Date.now()`만 직접 호출하면 콘솔에서 안전하게 mock할 수 없으므로, 주입 지점을 계약에 명시한다(계약 상세는 22 §5-2)
  - [ ] `docs/data/meta/freshness.json` 발행 신설 — **Settings ④(데이터 갱신 안내)의 단일 fetch 소스**. runlog는 그 생성 원료이며, 생성 시점은 `build.py` 공통 마무리 단계(규격은 21 §4)
  - [ ] v2 셸로 `docs/ta/index.html` 렌더(TA-PREVIEW + 정적 SLOT/ROADMAP)
- **산출물:** `docs/ta/index.html`, `preview.json`, `freshness.js`, `meta/freshness.json`.
- **완료 기준(DoD):**
  1. `/ta/`가 v2 셸로 렌더되고 TA-PREVIEW 카드가 KOSPI 실데이터(종가·이격·RSI·추세)를 표시한다.
  2. `?now=` 시계 주입 훅으로 강등이 재현된다 — TA 데이터군 T=24h(21 실측표) 기준: `?now=` 값을 `as_of`+25h로 주면 **DELAYED 배지 클래스**, `as_of`+73h로 주면 **STALE 강등 클래스**(24~72h=DELAYED, ≥72h=STALE — 4상태 정본의 T·3T)가 각각 표시된다.
  3. 공통 신선도 규칙 pytest가 통과한다.
- **검증 방법:** `preview.json` 스키마 검증. `/ta/?now=<ISO시각>` 3케이스(경과 <24h / 24~72h / ≥72h) 접속 → 배지 클래스가 기대값(FRESH 무배지 / DELAYED / STALE)과 일치하는지 확인. `pytest tests/test_freshness*.py`(신규). `meta/freshness.json` 존재·스키마 확인.
- **리스크·롤백:** 계약이 실화면에서 부족함이 드러날 위험 — 이것이 이 Phase의 **의도된 검증 목적**이다. 계약 결함 발견 시 Phase 0로 피드백(필드 추가/의미 정정)하고 재관통. 롤백은 신규 파일 삭제로 무영향(라이브 무간섭).
- **선행 조건:** Phase 0(계약), Phase 1(v2 셸·토큰).

### Phase 3 — 시세 유니버스 증분 확장 (Envelope 실데이터 검증)

- **목표:** 신규 수집기 없이 심볼만 추가해 계약을 20+ 지표로 실증한다.
- **작업:**
  - [ ] `config/markets.py`에 심볼 추가: KOSPI/KOSDAQ 현물(`^KS11`/`^KQ11`)·VIX(`^VIX`)·**MOVE(`^MOVE`)**·DXY(`DX-Y.NYB`)·Gold(`GC=F`)·Copper(`HG=F`)·**NatGas(`NG=F`)**·NQ선물(`NQ=F`)·미10Y(`^TNX`)·크로스환율·BTC(`BTC-USD`) — `^MOVE`·`NG=F`는 21 §2-2 요구 심볼이며 yahoo 소스이므로 본 Phase(수집기 신설 없는 심볼 증분)에 배정한다
  - [ ] `market_collector.collect()` out 딕트 확장 → `market_repository._NAMES/_CURRENCY` 등재
  - [ ] 스파크라인은 매 빌드 `history()` 재조회(누적 저장 금지)
- **산출물:** 확장 `market.json`(MOVE·NatGas 포함 21 §2-2 대조 가능), 지수 스파크라인 JSON.
- **완료 기준(DoD):**
  1. 신규 심볼이 **전량 Envelope 스키마를 통과**한다(컨테이너 스키마 경유).
  2. 실패 심볼은 가짜 0이 아닌 **None으로 강등**된다(validator가 제거).
  3. bp 변화 항목(미10Y 등)이 `change_abs`로 표기된다.
- **검증 방법:** 확장 `market.json` 컨테이너 스키마 검증. 특정 심볼을 의도적으로 실패시켜 해당 키가 산출물에서 누락(값 0 아님)됨을 확인. grep으로 `change_abs` 존재 확인. 심볼 목록을 21 §2-2와 1:1 대조.
- **리스크·롤백:** 심볼 8→20+ 증가로 호출량·빌드 시간·차단 리스크 상승 → 배치 조회·지수 백오프·실패 시 직전 캐시 유지(기존 팩트우선 원칙). 특정 심볼이 상시 실패하면 `config/markets.py`에서 제거(1줄)로 롤백, 다른 지표 무영향.
- **선행 조건:** Phase 0.

### Phase 4 — Dashboard(`/`) 치환 (라이브 #1, 자산 평문 선차단)

- **목표:** 최다 트래픽 랜딩을 v2로 치환한다(URL 불변). 현행 `dashboard.html` 36~88행의 Notion 자산 평문 렌더 구조(총 자산·유형별 금액·목표금액·현금흐름 — `{% if erp %}` 블록 실측)를 **코드가 자산을 노출하기 전에 선차단**한다.
- **작업:**
  - [ ] Dashboard 생성기 v2 재작성(Hero·한/미 지수·핵심뉴스·오늘 일정)
  - [ ] 절대 자산 금액 렌더 금지 — 상대값화 또는 제거(목표금액·투입원금 등 역산 가능값 포함)
  - [ ] `updown.js` 최초 구현 — 저장된 등락색 모드를 `[data-updown]`에 적용(값은 Phase 1 토큰에 이미 탑재, 토글 UI는 Phase 9 Settings)
  - [ ] 암호화 발행 정책(A+D) **착수/확정**(구현은 Phase 8)
- **산출물:** 신규 `docs/index.html`, `updown.js`.
- **완료 기준(DoD):**
  1. `/`가 v2 셸로 렌더되고 URL이 불변이다.
  2. 렌더된 `docs/index.html`에서 **자산 절대값·역산 가능값 grep이 0건**이다.
  3. Hero 데이터 결측 시 문장 행을 팩트 우선으로 생략한다(빈 문장 렌더 금지).
  4. `[data-updown]` 값을 한국↔글로벌로 바꾸면 등락 색이 실제로 뒤집힌다(스토리지 값 변경으로 확인 — 토글 UI는 Phase 9).
- **검증 방법:** `grep -E '[0-9]{3}[,0-9]*원|총자산|목표금액' docs/index.html` → 0건. 셀렉터로 Hero 결측 케이스 렌더 확인. 개발자도구에서 `data-updown` 속성 전환 → 등락 색 반전 확인.
- **리스크·롤백:** Hero 해석 문장이 AI 금지와 충돌 → 템플릿 조립 문장 + 미입력 시 행 생략(21 결측 문법). 랜딩 회귀 위험이 가장 크므로 → 치환 직후 `/index.html` 스냅샷을 보관, 결함 시 v1 생성기로 즉시 되돌림(생성기 파일 교체 단위).
- **선행 조건:** Phase 2·3, 암호화 정책 **결정**(구현 아님).

### Phase 5 — News(`/news/`) 치환 (라이브 #2)

- **목표:** 기존 URL을 유지한 채 4탭·행 펼침·키워드 레이더·날짜 아카이브를 도입한다.
- **작업:**
  - [ ] 6카테고리 → 4탭 배타 매핑(우선순위 규칙 macro > kr/us) — 탭 전환은 `tabs.js` 최초 구현
  - [ ] `NewsArticle`에 `level·impact_tags·first_seen_at` 추가(`from_dict` 하위호환)
  - [ ] `config/entities.py`(종목명→티커, 시총 상위 큐레이션) 신설
  - [ ] 일별 게재 카운터 상태 파일(유니크 수집 수·게재 수, 자정 KST 리셋)
  - [ ] 날짜 아카이브 `docs/news/YYYY-MM-DD/`(morning 일자 디렉터리 패턴 재사용)
  - [ ] "AI BRIEFING" → "모닝 브리핑" 개칭
- **산출물:** 신규 `docs/news/index.html` + 날짜 아카이브, `tabs.js`.
- **완료 기준(DoD):**
  1. `/news/`가 v2로 렌더되고 탭이 배타적이다(한 기사 1탭, 속보만 통합).
  2. 기존 400건 저장소 기준 회귀 0(누락 기사 없음).
  3. L3 판정이 **일 상한(예: 5건)을 넘지 않는다**(초과분 L2 강등).
  4. `news.yml` 30분 cron 정상, `test_news_categorize.py`가 하위호환으로 통과.
- **검증 방법:** 탭별 기사 집합의 교집합 = ∅ 확인. L3 카운트 상한 assert. `pytest tests/test_news_categorize.py`.
- **리스크·롤백:** 상세 요약 3줄이 본문 미저장·no-AI·저작권과 충돌 → 펼침 영역을 RSS 요약 전문(≤280자)+시장 스냅+칩으로 재정의, 빈약하면 요약 블록 생략(디자인 "최대 3줄"로 완화). 배타 분류 전환이 기존 UX와 단절 → AI/반도체는 탭이 아닌 영향시장 배지·키워드로 흡수(사전 재사용, 데이터 손실 0). 롤백은 생성기·템플릿 교체 단위.
- **선행 조건:** Phase 2.
- **정리점(중요):** Dashboard(Phase 4)+News(Phase 5)가 모닝 콘텐츠를 커버 완료 → **모닝 생성기 발행 중단 판단 시점**(§5 참조).

### Phase 6 — Macroeconomics(신규 `/macro/`, 독립 트랙)

- **목표:** 시세 유니버스에 의존하지 않는 독립 거시 트랙을 세운다. Phase 7과 병렬 가능.
- **작업:**
  - [ ] 수집기: FRED(CPI/PCE/GDP/UNRATE/PAYEMS + release dates)·ECOS(국고채·기준금리)·Upbit(BTC/KRW·김치 프리미엄)
  - [ ] 발표치·이전치·추이(YoY 자체 계산)·다음 발표일
  - [ ] **예상치 = 무료 소스 부재 → 수동 YAML 옵션(미입력 시 열 생략)**
  - [ ] `macro.yml` 60분 cron 신설(API 키 env 주입)
- **산출물:** `docs/macro/`, `macro/indicators.json`, `macro/calendar.json`.
- **완료 기준(DoD):**
  1. 확보 지표가 렌더되고, **예상치 미입력 칸은 빈칸이 아니라 열/행 생략**된다.
  2. STALE 강등이 정상 동작한다(`?now=` 훅으로 재현 — Phase 2와 동일 절차, 문턱값은 21 실측표의 거시 행).
  3. 캘린더가 발표 전→후를 클라이언트 판정으로 전환한다.
- **검증 방법:** 예상치 미입력 상태에서 렌더 → 빈 셀 grep 0. `indicators.json` 스키마 검증. `?now=` 주입으로 발표시각 전후 캡슐 전환 확인.
- **리스크·롤백:** 예상치·VKOSPI·PMI·동결확률 등 무료 소스 부재 → 변동성 섹션 3장 축소, PMI 행 제외, 예상치 옵션화(21 결측 문법). 소스 API 스키마 변경 → 실패 시 카드 생략(None 원칙). 독립 트랙이라 롤백은 `/macro/` 타깃·`macro.yml` 제거로 타 페이지 무영향.
- **선행 조건:** Phase 0. (6 ∥ 7)

### Phase 7 — Stock + Stock Hub + Financial Statements + 글로벌 검색 (최중량 데이터, 후순위)

- **목표:** 데이터 폭이 가장 큰 그룹. 화면 현대화가 끝난 뒤 착수해 데이터 리스크가 전체 이행을 볼모잡지 않게 한다. 00 §7-2·05·06의 3클릭 시나리오가 전제하는 **글로벌 검색(커맨드 팔레트)** 을 이 Phase에서 함께 완성한다(search-index 데이터와 팔레트 UI를 분리 배정하지 않는다).
- **작업:**
  - [ ] `config/universe.py`·`config/themes.py`(테마→종목 수동 매핑) 신설
  - [ ] 수집기: KRX/us_ranking·DART·EDGAR / 랭킹·테마 calculator
  - [ ] 발행: `docs/data/stock/rankings.json`·허브 종목별 JSON·`search-index.json`
  - [ ] 재무 성장·수익·안정·현금흐름·밸류 calculator(결정론적 룰)
  - [ ] `panel_slot` 전역 패널 + fetch 로더 + 해시 라우팅 + 포커스 트랩
  - [ ] **`search.js` 커맨드 팔레트** — Ctrl/⌘+K 오픈, 그룹 3종(종목/뉴스/페이지, 그룹당 최대 5건), 위→아래 키보드 탐색·Enter·Esc(00 §7-2), **종목 항목 Enter → Hub 패널 오픈(`#hub=` 해시 세팅)** 연동
  - [ ] 소급 불가 히스토리 `data/history/` 커밋 — 대상은 **전일 순위·PER/PBR 밴드 한정**(**`git add` 확장 결정 선행**, 자산 스냅샷은 제외 — §0-1 정본 3)
- **산출물:** `docs/stock/`, `docs/financials/`, 종목별 JSON, `search-index.json`, `search.js`, `stock.yml`.
- **완료 기준(DoD):**
  1. 한/미 TOP30 ×2가 렌더되고 **모집단 캡션**("유니버스 N종목 중")이 붙는다.
  2. Stock Hub가 트리거·딥링크(해시)·포커스 트랩으로 동작하고, 유니버스 밖 종목은 빈 상태를 표시한다.
  3. **Ctrl/⌘+K 입력 시 커맨드 팔레트가 열리고**, 검색어 입력 → 그룹 3종 결과 표시 → **종목 선택(Enter) 시 URL 해시가 `#hub=<티커>`로 세팅되며 Hub 패널이 열린다.** Esc로 닫힌다.
  4. FS 5년 카드가 렌더되고, **업종 평균 결측 시 자사 5y 단독 판정**으로 강등된다.
- **검증 방법:** rankings/hub/search-index 스키마 검증. 해시 딥링크로 패널 자동 오픈 확인. Ctrl+K→팔레트 오픈→"삼성" 입력→종목 Enter→`#hub=` 해시·패널 오픈을 브라우저에서 순서대로 확인. 업종 평균 없는 종목의 판정 캡션 확인. Tab 키 포커스가 패널 내부에 갇히는지 확인.
- **리스크·롤백:** "장중 20분 FRESH"는 cron 지연(20분~3.7h)상 보장 불가 → 목표를 "장중 30~60분 + 마감 후 1회"로 낮추고 CLOSED-SNAPSHOT을 1급 상태로 운용. 미국 "전시장 TOP30" 무료 불가 → "유니버스 내 TOP30"으로 정의 변경(캡션 명시). 5년 PER 밴드·업종 평균 소급 불가 → 자체 근사·초기 결측 캡션. 롤백은 신규 타깃·`stock.yml` 제거 + `panel_slot`은 v2 셸 블록이므로 미사용 시 무영향. 팔레트는 독립 JS 모듈이므로 결함 시 `search.js` 미로드로 헤더 검색만 비활성(타 기능 무영향).
- **선행 조건:** Phase 0(계약)·1(panel_slot)·3(유니버스는 Phase 3 시세 위 확장). (6 ∥ 7)

### Phase 8 — Asset + Portfolio + `/trades` v2 (4계좌 자동 수집, 비번 게이트)

- **목표:** 개인 자산 평문 공개 사고를 코드 이전에 차단한다. 암호화 발행 정책(A+D)을 선확정한 뒤 구현한다. 자산 파이프라인은 **4계좌 전량 자동 수집**(§0-1 정본 2)이며, 공개 서비스인 매매일지(`/trades`)는 이 Phase에서 **공개 v2 페이지로 치환**한다(게이트 없음).
- **작업:**
  - [ ] 데스크톱 `app/sync.py` 확장 — **4계좌 전량 자동 수집**: ① 키움증권 잔고 TR(로컬 32-bit, 단타·스윙 주력) ② 한국투자 위탁 KIS REST(미국주식 전용) ③ 한국투자 ISA KIS REST(ETF 절세) ④ BYBIT REST(암호화폐). 수기 입력 파일 경로는 설계상 존재하지 않는다(KB 삭제로 소멸). 자산 신선도는 **T=24h 단일 규칙**(21 정본 — 계좌별 이원화 규칙 없음)
  - [ ] `data/snapshots/` 1일 1행 append — **로컬 전용 원장(.gitignore, 커밋 금지)**. 90일 히스토리 파생은 데스크톱에서 로컬 원장으로 계산해 **암호문 payload 내부**에 포함
  - [ ] **`.gitignore`에 `data/snapshots/` 명시 추가** — 현행 `.gitignore`는 `data/cache/` 커밋을 허용하는 구조이므로, 명시 제외 없이는 실제로 커밋된다(오커밋 1회 = git 히스토리 영구 사고)
  - [ ] **A안: PBKDF2/Argon2 + AES-GCM `assets.enc.json`** + **D안: 상대값만 공개**
  - [ ] 계좌 카드 필드 요구(08·09 스펙 준수): **한국투자 위탁 카드는 USD/KRW 듀얼 표시 + 적용환율이 필수 필드**(미국주식 전용 확정에 따라 옵션이 아님), 키움=잔액+전일 대비, ISA=ETF 구성·만기 관점, BYBIT=USDT 평가액+원화 환산(24시간 시장·스냅샷 라벨)
  - [ ] WebCrypto 게이트(복호화 성공 = 인증)
  - [ ] **평문 오커밋 방지 이중 가드** — (a) pre-commit 훅: 절대금액 패턴·`data/snapshots/` 경로 유입 차단, (b) **CI 게이트: reusable workflow 공통 단계에 평문 패턴 grep(매칭 시 빌드 실패, `data/snapshots/` 경로 차단 포함)**. pre-commit은 클론마다 수동 설치라 누락 시 무력이고 github-actions bot 커밋은 훅을 거치지 않으므로 CI 게이트가 필수 백스톱이다. **데스크톱 앱(app/) push 절차 문서에 훅 설치 확인 단계를 명기**
  - [ ] `/trades` 공개 v2 치환 — 매매일지를 v2 셸로 재생성(URL 유지·게이트 없음). ※ design/09 Portfolio에는 매매일지 화면이 정의되어 있지 않고(§향후 개선의 실현손익 조인 가능성만 언급) Portfolio는 비번 게이트 뒤이므로, "Portfolio 흡수" 안은 공개 서비스를 잠금 화면 뒤로 사라지게 해 기각한다. `trades.json` 공개 범위는 §2 비코드 결정을 따른다
- **산출물:** `docs/asset/`, `docs/portfolio/`, `assets.enc.json`, 신규 `docs/trades/`(v2), `.gitignore` 개정, CI 가드 단계.
- **완료 기준(DoD):**
  1. 게이트 밖(공개 JSON·HTML) 어디에도 **자산 절대값·역산 가능값(자산 총액·계좌 잔고·목표금액·투입원금 패턴) grep이 0건**이다. 매매일지의 매매 단위 기록은 §2에서 확정한 공개 범위 결정을 따르며, 그 결정에 따라 grep 패턴 목록을 고정해 함께 검증한다.
  2. 올바른 passphrase 복호화 = 열람이 성립한다.
  3. KDF·passphrase 정책이 반영된다(Settings의 "4자 이상" 문구 개정).
  4. **4계좌(키움·한투 위탁·한투 ISA·BYBIT) 스냅샷이 데스크톱 실행 1회로 전량 자동 생성**되고, 한투 위탁 항목에 USD 원값·적용환율·KRW 환산이 모두 존재한다.
  5. `git check-ignore data/snapshots/<파일>` 이 무시됨을 반환한다(.gitignore 등재 확인).
  6. **CI 게이트가 평문 주입 케이스에서 실패한다** — 테스트 브랜치에 평문 자산 패턴/`data/snapshots/` 파일을 의도적으로 넣으면 워크플로가 fail로 종료됨을 확인.
  7. 히스토리 파생(전일 대비·90일 추이)이 로컬 원장에서 계산되어 암호문 payload 내부에서만 제공된다(공개 채널에 파생 절대값 부재).
- **검증 방법:** 공개 산출물 전체 grep(확정된 패턴 목록). pre-commit 훅에 평문 자산 필드 감지 케이스 통과 + `data/snapshots/` 스테이징 시 커밋 거부 확인. CI 평문 주입 브랜치 fail 확인. 잘못된 passphrase에서 복호화 실패 확인. 데스크톱 1회 실행 후 스냅샷 행의 계좌 키 4종 존재 확인.
- **리스크·롤백:** 정적 게이트는 접근 제어가 아니다 → A(암호화)로 실질 기밀성, D(상대값)로 공개 뷰 성립, 강한 KDF 필수(오프라인 무차별 대입 대비). passphrase 변경 = 데스크톱 재암호화(Settings 변경 모달을 클라이언트만으로 완결 불가 — 문서 정정). 평문 오커밋 시 git 히스토리 영구 잔존 → **pre-commit + CI 이중 가드가 최후 방어선**, 이것이 DoD 게이트. KIS·Bybit API 장애 시 → 직전 스냅샷 유지 + STALE 정직 노출(가짜값 금지). 일정 6종은 DART 3종으로 축소. 롤백은 신규 타깃 제거 + 데스크톱 수집 확장 비활성화(매매일지는 v1 생성기 복귀).
- **선행 조건:** Phase 0(계약), Phase 1·2(v2 셸·`freshness.js` — 게이트 화면과 STALE 정직 노출이 소비), 암호화 정책 결정(Phase 4에서 착수), `/trades` 공개 범위 결정(§2).

### Phase 9 — Settings + v1 셸 은퇴 (공존 종료 — 소스 한정)

- **목표:** 마지막 v2 페이지를 올리고 이중 유지보수를 종료한다. **은퇴는 소스 한정이다** — 아카이브가 참조하는 배포 자산은 동결 유지한다(§0-1 정본 4).
- **작업:**
  - [ ] Settings 6섹션(등락 모드·시계·마스킹·갱신 안내·관심 테마·초기화 — localStorage/sessionStorage). 등락 모드 토글 UI는 Phase 4의 `updown.js`를 소비, ④ 갱신 안내는 Phase 2의 `docs/data/meta/freshness.json`을 단일 fetch 소스로 사용
  - [ ] 전 페이지 v2 확인 후 **v1 셸 소스 은퇴**: `templates/base.html` 제거 + `static/` 소스본에서 v1 전용 자산(`style.css`·`app.js` 소스본) 제거·`copy_static` 배포 목록에서 제외
  - [ ] **`docs/static/css/style.css`는 아카이브 전용 동결 자산으로 영구 배포 유지** — 실측상 `docs/morning/2026-07-01/index.html` 등 동결 아카이브가 `href="../../static/css/style.css"`를 하드코딩 참조하므로, 이 파일이 사라지면 '영구 보존' 대상 아카이브 전체가 무스타일로 깨진다(HTTP 200이어도 사용자 가치 훼손). `copy_static` 개정 시 docs/ 기존 파일을 삭제·정리하지 않음을 보장하고, **신규 페이지의 참조만 금지**한다
  - [ ] `/ai-office` 최종 거취 확정(리다이렉트 or 흡수 — `/trades`는 Phase 8에서 공개 v2 치환 완료)
- **산출물:** `docs/settings/`, v1 셸 소스 제거 커밋(동결 자산 무변경).
- **완료 기준(DoD):**
  1. **소스 범위 v1 셸 참조 0건** — `grep -rn "base.html\|style.css" templates/ generators/` 결과 0건. ※ `docs/` 아카이브 HTML의 참조는 동결 예외이므로 grep 범위에 포함하지 않는다(경로 무제한 grep은 아카이브 때문에 영원히 달성 불가한 문장이라 채택하지 않는다).
  2. **소스 범위 hex 0건**(Phase 1 DoD 3에서 이관) — `grep -rEn '#[0-9a-fA-F]{3,6}' templates/ static/` 결과가 `tokens.css` 원시 팔레트 정의부 밖 0건. `docs/`는 동결 산출물이므로 제외.
  3. 전 v2 페이지가 단일 토큰 시스템(`tokens.css`)을 참조하고 사이트 전역 nav가 `config/nav.py` 단일 소스에서 나온다.
  4. 기존 dated URL(`/morning/YYYY-MM-DD/` 등)이 **전수 HTTP 200**이다.
  5. **아카이브 스타일 정상 렌더** — `/morning/2026-07-01/` 등 표본 아카이브 페이지에서 `docs/static/css/style.css`가 200으로 로드되고 스타일이 적용된 상태로 렌더된다(무스타일 아님을 육안/스냅샷 확인).
  6. Settings ①(등락 모드) 토글이 실제로 전 페이지 등락 색을 전환한다(Phase 1 값 + Phase 4 `updown.js`의 종착 검증).
- **검증 방법:** 경로 스코프를 명시한 셸 참조 grep·hex grep. 배포 후 dated URL 목록에 대해 상태코드 200 일괄 확인 + 표본 아카이브의 CSS 로드·렌더 확인. nav 렌더 단일 소스 확인. Settings 토글 조작 → `[data-updown]` 전환 → 색 반전 확인.
- **리스크·롤백:** v1 소스 조기 제거로 미이행 페이지가 깨질 위험 → "전 페이지 v2 확인"을 제거의 선행 게이트로 고정. 동결 자산(`docs/static/css/style.css`)을 실수로 삭제·덮어쓸 위험 → DoD 5(아카이브 렌더)가 게이트이며, 사고 시 git에서 해당 파일만 복원. 문제 발견 시 `templates/base.html`·소스 `style.css` 복원(git revert 1커밋)으로 공존 재개.
- **선행 조건:** Phase 2~8 완료.

---

## 4. 기존 URL 보존 매트릭스 + 페이지 최종 거취

원칙: **모든 기존 URL과 아카이브는 전수 보존한다.** 치환은 같은 경로에 v2 산출을 덮는 방식이며, 은퇴는 meta-refresh/리다이렉트로 처리한다. 동결 아카이브가 참조하는 `docs/static/css/style.css`는 영구 배포 자산이다(§0-1 정본 4).

| 기존 URL | 현행 생성기 | 로드맵 후 상태 | 조치 Phase | 비고 |
|---|---|---|---|---|
| `/` (`docs/index.html`) | dashboard | **v2 치환**(URL 불변) | 4 | 자산 평문 선차단 동반 |
| `/morning/YYYY-MM-DD/` | morning | **아카이브 영구 보존(동결)** | (보존) | 신규 발행만 중단(§5) · 동결 style.css 참조 유지 |
| `/morning/` (아카이브 인덱스) | morning `_archive()` | 유지 | (보존) | 기존 일자 링크 200 유지 |
| `/news/` (`docs/news/index.html`) | news | **v2 치환**(URL 유지) + 신규 `/news/YYYY-MM-DD/` | 5 | morning 일자 패턴 재사용 |
| `/trades/` | trades | **공개 v2 페이지로 유지·치환**(URL 유지·게이트 없음) | 8 | design/09에 매매일지 화면이 없고 Portfolio는 비번 게이트 뒤이므로 "흡수" 안 기각. `trades.json` 공개 범위는 §2 비코드 결정 |
| `/ai-office/` (+ `runlog.json`) | ai_office | **최종 거취 확정**(리다이렉트 or 흡수). runlog는 **`freshness.json`의 생성 원료로 유지** | 9 | Settings ④의 fetch 소스는 `docs/data/meta/freshness.json`(Phase 2 최초 발행)이며 runlog 직접 fetch가 아니다 |
| `/ta/` | (신규) | 신설 | 2 | 파일럿 |
| `/macro/` | (신규) | 신설 | 6 | 독립 트랙 |
| `/stock/`·`/financials/` | (신규) | 신설 | 7 | 최중량 데이터 + 글로벌 검색 |
| `/asset/`·`/portfolio/` | (신규) | 신설(비번 게이트) | 8 | A+D 암호화 · 4계좌 |
| `/settings/` | (신규) | 신설 | 9 | 마지막 v2 페이지 |

`/ai-office`의 최종 거취는 **Phase 9에서 확정**한다(리다이렉트 or 페이지 흡수). 어느 경우에도 기존 URL은 200 또는 meta-refresh로 살아 있어야 하며 죽은 링크를 남기지 않는다. `/trades`는 Phase 8에서 공개 v2로 치환되므로 별도 거취 결정이 필요 없다(기존 3서비스 모두 수용처 확정: 모닝→아카이브 동결, 뉴스→v2 치환, 매매일지→공개 v2 치환).

---

## 5. 모닝 생성기 "가동 유지 · 발행 중단" 판단 시점

- **판단 시점:** **Phase 5 완료 정리점.** Dashboard(Phase 4)와 News(Phase 5)가 모닝 리포트의 콘텐츠(간밤 지수·핵심 뉴스·오늘 일정·브리핑)를 전부 커버하는 시점.
- **결정 내용:** 모닝 파이프라인(`get_market`·`get_news`·runlog 계측)과 06:30 KST 워크플로는 **가동을 유지**한다 — 데이터 수집·신선도 계측은 Dashboard/News가 계속 소비하기 때문이다. **중단하는 것은 신규 `/morning/YYYY-MM-DD/` 페이지 발행뿐**이다.
- **보존 계약:** 기존 `/morning/` 아카이브(2026-07-01~ 발행분)는 **영구 보존(동결)** 하며 Phase 9 DoD의 "dated URL 전수 200 + 아카이브 스타일 정상 렌더"에 포함된다. 아카이브가 참조하는 `docs/static/css/style.css`도 동일하게 영구 배포한다.
- **비고:** 발행 중단은 워크플로 삭제가 아니라 morning 생성기의 페이지 write 단계만 비활성화하는 방식으로, 데이터 파이프라인 회귀 위험 없이 되돌릴 수 있게 둔다.

---

## 6. '하지 않을 것' (스코프 아웃)

이 로드맵이 **의도적으로 하지 않는** 것들. 각 항목은 무료·1인·정적·no-AI 원칙 또는 리스크 통제상의 결정이다.

- **`base.html`(v1 셸) 조기 수정·삭제** — Phase 9 이전까지 소스 동결. 공존이 연속성의 핵심 장치다. Phase 9의 제거도 **소스 한정**이며 `docs/static/css/style.css`는 아카이브 동결 자산으로 영구 유지한다.
- **동결 아카이브의 v2 재생성·스타일 이관** — 기존 발행 `/morning/YYYY-MM-DD/` HTML은 손대지 않는다. 재생성은 '영구 보존' 계약 위반 리스크만 만든다.
- **라이트 테마 값 채움·3계층 토큰 완전 추상화** — 라이트 테마는 스위칭 슬롯만 예약하고 유예(과설계 회피, 다크 우선). 단, **글로벌 등락색 `[data-updown]` 값은 유예 대상이 아니며 Phase 1에서 채운다** — Phase 9 Settings ①(등락 모드 토글)이 약속하는 사용자 가치의 동작 전제이기 때문이다(값 채움 Phase가 없으면 토글이 동작 불능).
- **"라이브" 실시간 시세** — 모든 값은 배치 스냅샷이다. 야간선물 세션 중 `● LIVE`(상태 A)·T=10분은 지원 범위에서 제외(Kiwoom 데스크톱 수동 의존).
- **AI 생성 문장** — Hero/브리핑/FS 요약은 전부 규칙 기반 템플릿 조립. AI API 미도입.
- **경제지표 예상치·서프라이즈 자동 수집** — 무료 공식 소스 부재. 수동 YAML 옵션(미입력 시 열 생략), 스크래핑 미채택(ToS·차단 리스크).
- **미국 "전시장" 랭킹, KRX 실시간 수급·거래대금·시간외 단일가** — 무료 경로 부재. 유니버스 내 랭킹으로 정의 변경, 수급 불릿은 뉴스 헤드라인 기반으로 대체.
- **VKOSPI·S&P Global PMI·CME 동결확률·IR/규제/락업 일정** — 취약 크롤링·유료. 섹션 축소 또는 Coming Soon.
- **시계열 자체 누적 저장** — 소스 API가 히스토리를 주는 항목은 매 빌드 재조회. `data/`에 커밋하는 것은 소급 불가 데이터 중 **전일 순위·PER/PBR 밴드로 한정**한다. **자산 스냅샷 원장은 커밋 대상이 아니라 로컬 전용(`.gitignore`)이다** — 90일 히스토리는 암호문 payload 내부로만 발행(§0-1 정본 3).
- **개인 자산의 서버 기반 접근 제어** — 무료 정적 원칙상 불가. 클라이언트 암호화(A) + 상대값 공개(D)로 대체, 게이트는 UX 계층으로만 규정.
- **CI에 계좌 자격증명·평문 자산 배치** — 절대 금지. 자산 수집·암호화는 데스크톱 전용(4계좌 전량: 키움 TR·KIS×2·Bybit). CI에는 평문 차단 grep 게이트만 둔다(Phase 8).
- **모바일 퍼스트·반응형 전면 재설계** — Desktop First 유지(디자인 기준). 기존 720px 브레이크포인트 수준 유지.

---

## 7. 마일스톤별 사용자 가치 (각 Phase 후 새로 할 수 있는 것)

| Phase | 완료 후 사용자가 새로 할 수 있는 것 |
|---|---|
| 0 | (사용자 화면 무변화) — 이후 모든 시세가 "값+기준시각+신선도+세션"을 일관되게 갖추는 토대가 생긴다. 야간선물 stale 오독 방어가 전 지표로 확장될 준비 완료. |
| 1 | (사용자 화면 무변화) — 신규 사이드바 셸이 준비되어, 다음 Phase부터 나타나는 새 페이지들이 일관된 내비게이션·토큰 위에 올라온다. 등락색 한국/글로벌 두 값이 토큰에 탑재되어 이후 토글의 기반이 된다. |
| 2 | **KOSPI 기술 지표(종가·이평 이격·RSI·추세)를 `/ta/`에서 본다.** 처음으로 "지금 이 값이 신선한가(FRESH/DELAYED/STALE/CLOSED-SNAPSHOT)"를 화면 배지로 판단할 수 있다. |
| 3 | 대시보드·거시에 쓰일 20+ 지표(KOSPI/KOSDAQ 현물·VIX·MOVE·DXY·금·구리·천연가스·미10Y·BTC·크로스환율)가 신선도 판정과 함께 확보된다. bp 변화·절대 등락폭을 정직하게 표기. |
| 4 | **새 랜딩(`/`)에서 한·미 지수, 핵심 뉴스, 오늘 일정을 한 화면에서 본다.** 개인 자산 절대값이 공개 페이지에서 사라진다(프라이버시 사고 선차단). 등락색이 저장된 모드대로 적용된다. |
| 5 | **뉴스를 미국/한국/거시/속보 4탭으로 배타 분류해 읽고**, 행을 펼쳐 요약·시장 스냅·관련 종목을 본다. 키워드 레이더·날짜별 아카이브·중요도 등급으로 탐색. |
| 6 | **거시 대시보드(`/macro/`)에서 미 지표(발표치·이전치·추이·다음 발표일)·금리·환율·원자재·BTC(김치 프리미엄)를 본다.** 발표 전/후가 자동 전환. |
| 7 | **거래대금 TOP30(한/미)과 테마 스크리너를 보고, 종목을 클릭해 전역 Hub 패널(시세·일정·뉴스·TradingView·재무 딥링크)을 3클릭 이내로 연다.** **어느 페이지에서든 Ctrl/⌘+K로 종목·뉴스·페이지를 검색하고 Enter 한 번으로 Hub를 연다.** 재무제표 5년 카드(성장·수익·안정·현금흐름·밸류)를 판정과 함께 확인. |
| 8 | **비밀번호로 개인 자산(총자산·4계좌별 — 키움 단타·스윙 / 한투 위탁 미국주식 USD·KRW 듀얼 / 한투 ISA ETF / BYBIT 암호화폐 — 목표 달성률·90일 추이)과 포트폴리오(보유 종목·손익·비중)를 열람한다.** 게이트 밖에는 절대값이 존재하지 않아 어느 기기에서든 안전하게 확인. 매매일지는 새 v2 화면으로 계속 공개 열람. |
| 9 | **설정에서 등락 색상 모드·시계·마스킹·관심 테마를 직접 바꾼다**(토글이 Phase 1 토큰 값 + Phase 4 `updown.js` 위에서 실제 동작). 사이트 전 페이지가 단일 토큰·단일 내비게이션으로 통일되고, 기존 리포트 아카이브도 스타일까지 그대로 살아 있다. |

---

*본 문서는 지침 A(로드맵)에 해당한다. 필드 정의·JSON Schema(envelope + market 컨테이너)·소스별 신선도 실측표(DELAYED 열 포함)·결측 강등 문법·암호화 파라미터는 **21 데이터 요구 명세**를, `base_v2` 블록체계·`config/nav.py` 계약·토큰 스코프·`build.py` 레지스트리·`freshness.js` 계약(`?now=` 훅 포함)·발행채널·워크플로 구성은 **22 아키텍처**를 참조한다. 교차 상충 해소 결과는 §0-1 정본 선언에 요약되어 있다.*
