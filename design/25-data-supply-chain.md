# 25. 데이터 공급망 아키텍처 v1.0 — 현행 분석과 마이그레이션 계획

본 문서는 "Data Supply Chain Architecture v1.0" 스펙(외부 소스 → Collectors → Validators →
Normalizers → Cache → Calculators → Generators → GitHub Pages)을 기준으로 현행 코드를 감사하고,
**전면 재작성 없이** 점진 이관하는 계획을 확정한다. 코드는 아직 수정하지 않았다 — 본 문서 승인
후 Phase 단위로 구현한다(design/23·24와 동일 절차).

핵심 결론: 현행 파이프라인(collectors → validators → repositories → calculators → generators)은
스펙과 **대부분 정합**한다. 위반은 3가지 축이다 — ① 캐시 계층이 3곳으로 분산되고 일부 도메인은
캐시 없이 곧장 발행물(docs/data/)에 쓴다, ② morning/news만 공용 파이프라인(pipelines.py)을 쓰고
macro/stock/ta/financials는 수집→검증→저장 흐름을 생성기 안에 인라인 중복한다, ③ 생성기가
컬렉터 내부(SERIES 상수·enabled())에 직접 의존한다. 이 3가지를 고치면 스펙의 골격이 완성된다.

## 0. 검증된 현행 앵커 사실

실제 파일 확인 결과이며 설계의 전제다.

| 항목 | 확인된 사실 | 스펙 대비 판정 |
|---|---|---|
| 계층 구조 | collectors/ validators/ repositories/ calculators/ generators/ 물리 분리, build.py가 조립 루트 | **정합** (Normalizers 역할은 repositories가 겸함) |
| 공용 파이프라인 | `generators/pipelines.py`에 market·news 2개만 존재 | **부분 정합** — macro/stock/ta/financials 미포함 |
| 생성기의 컬렉터 직접 import | `generators/{macro,stock,ta,financials,news_v2}/generate.py` 5곳 | **위반** — "Never call APIs directly from generators" |
| 캐시 위치 | ① `cache/`(market·news·vault) ② `data/cache/`(market_last, kiwoom_night — CI↔데스크톱 전달) ③ `docs/data/`(macro·stock·ta·financials·asset — 캐시 없이 직행) | **위반** — "Everything must pass through cache" |
| 검증 | 도메인별 validators 7개, 불합격 → None/생략(가짜 값 금지) | **정합** |
| 무효 데이터의 캐시 보호 | market_last 26h 상한, asset 전계좌 실패 시 발행 skip 등 도메인별 개별 구현 | **부분 정합** — 공통 규칙 없음, docs/data 직행 도메인은 last-good 비교 불가 |
| 테마 | `calculators/themes.py`(뉴스 빈도 기반) + `config/themes.py`(테마→종목 수기 매핑, design/21 §7-1) | **긴장** — §5 결정 필요 |
| 이벤트 | `config/economic_calendar.py`에 FOMC 2026 일정 하드코딩(출처 URL·확인일 명기) + FRED next_release 수집 | **긴장** — §5 결정 필요 |
| 스케줄 | 도메인별 cron 분리(news 30분 · macro 60분 · stock 장중 · financials/asset 일1회) | **충돌** — 스펙 "12시간 00:00/12:00", §5 결정 필요 |
| Notion | 실사용 없음(migrate_notion_watchlist.py는 일회성 이관 스크립트). 포트폴리오·저널의 실소스는 Kiwoom + TH_DATA vault | **충돌** — 스펙 "Notion is backend database", §5 결정 필요 |
| Goal | `config/settings.py`의 `ASSET_GOAL_KRW` 단일 값 | 독립 도메인 없음 — §5 결정 필요 |
| 프로바이더 추상화 | 없음. 단, 컬렉터 모듈 자체가 소스별 격리 계층(market_collector 안에 Yahoo→Frankfurter→ExchangeRate-API 폴백 내장) | **부분 정합** — §3-3에서 경량 계약으로 해소 |

## 1. 아키텍처 위반 상세

### 1-1. 생성기 시점 수집 (스펙: Generators may only read cache)

`generators/macro/generate.py`가 대표 사례다: `_build_fred()/_build_ecos()/_build_upbit()`가
생성기 안에서 수집→검증을 수행하고, 곧바로 `macro_repository.persist()`가 **캐시를 거치지 않고**
`docs/data/macro/*.json`(발행물)에 쓴다. stock·ta·financials도 동일 패턴이다.

결과: ① 수집 실패가 렌더 실패와 결합된다(스펙의 단계 분리 이유). ② last-good 캐시가 없어
"Invalid data must never overwrite valid cache" 규칙을 적용할 물리적 장소가 없다. ③ 같은
수집→검증→저장 골격이 생성기 4곳에 인라인 중복된다(morning/news는 pipelines.py로 이미 해소).

### 1-2. 캐시 3분산

| 위치 | 내용 | 성격 |
|---|---|---|
| `cache/` (gitignore) | market.json, news*.json, vault_*.json | 실행 간 로컬 캐시 |
| `data/cache/` (커밋) | market_last.json, kiwoom_night.json | CI↔데스크톱 **전달 채널** |
| `docs/data/` (커밋·발행) | macro/stock/ta/financials/asset JSON | 발행물인데 캐시 역할 겸함 |

스펙의 단일 캐시 계약이 없어서, 새 도메인을 추가할 때마다 저장 위치를 재발명한다.

### 1-3. 생성기 → 컬렉터 내부 결합

`generators/macro/generate.py`가 `fred_collector.SERIES`·`fred_collector.enabled()`를 템플릿
컨텍스트에 직접 주입한다. 컬렉터의 내부 상수가 바뀌면 생성기가 깨진다 — 스펙의 "No other
module should notice the change"(프로바이더 교체 시) 위반. 시리즈 목록·활성 여부는 캐시
메타데이터로 내려보내야 한다.

### 1-4. 중복 로직 목록

- 수집→검증→저장 인라인 골격 4벌(macro/stock/ta/financials 생성기) — pipelines.py 미사용.
- runlog.run_step 폴백 패턴이 생성기·build.py·pipelines.py에 산재(공통 헬퍼 없음 자체는 허용
  범위이나, 도메인 파이프라인으로 흡수되면 자연 소멸).
- 신선도(as_of·max age) 판정이 market_collector(26h)·asset(24h)·freshness_meta.py에 각각 존재
  — config/freshness.py로 계약은 있으나 적용 지점이 분산.

## 2. 목표 구조 (스펙 사상(寫像))

스펙 8단계를 현행 5계층에 다음과 같이 사상한다. **디렉터리 개편은 하지 않는다** — 물리 이동
없이 계약만 세운다(유지보수 최우선, strangler 원칙 계승).

```
스펙                 현행 사상
Collectors     →     collectors/          (소스별 격리 — 프로바이더 어댑터 겸임, §3-3)
Validators     →     validators/          (변경 없음)
Normalizers    →     repositories/ 의 to_*() 변환부   (모델 변환 = 정규화)
Cache          →     repositories/ 의 persist부를 cache 계약으로 통일 (§3-1)
Calculators    →     calculators/         (변경 없음)
Generators     →     generators/          (캐시 읽기 전용으로 격하, §3-2)
GitHub Pages   →     docs/                (발행 = 캐시 → docs/data 복사·암호화)
```

## 3. 마이그레이션 계획 (Phase별, 각각 독립 배포 가능)

### Phase A — 캐시 계약 통일 (위반 1-2 해소)

1. `utils/domain_cache.py` 신설: `save(domain, body)` / `load(domain)` / 도메인당 파일 1개
   (`cache/{domain}.json`) / envelope(`as_of`, `source`, `items`) 강제.
2. **last-good 규칙을 여기 1곳에 구현**: 새 body가 검증 실패(빈 값·필수 결측)면 기존 캐시를
   덮지 않고 사실대로 로그. 도메인별 개별 구현(1-2)은 이 계약으로 수렴.
3. macro/stock/ta/financials repositories의 persist를 "캐시 저장 → 발행 복사" 2단계로 분리.
   `docs/data/`는 **발행 단계의 출력**으로만 남는다(캐시 역할 박탈).
4. `data/cache/`(CI↔데스크톱 전달)는 성격이 다르므로 **유지** — 명칭만 문서로 고정(전달 채널).
5. TH_DATA 활용(사용자 승인 완료): **원장·사용자 데이터**(저널, 워치리스트, 자산 스냅샷 로컬
   원장)는 TH_DATA에 두어도 된다. 단 **CI가 만드는 캐시는 저장소 안에 남긴다** — GitHub
   Actions는 ai_trading_assistant 저장소만 체크아웃하므로 TH_DATA를 볼 수 없다(데스크톱 전용
   데이터만 TH_DATA 이전 후보).

완료 기준: 전 도메인이 `cache/{domain}.json`을 경유하고, `docs/data/` 쓰기는 발행 함수 1곳뿐.

### Phase B — 도메인 파이프라인 추출 (위반 1-1·1-4 해소) — **완료(§10)**

1. `generators/pipelines.py`에 `get_macro()/get_stock()/get_ta()/get_financials()` 추가 —
   기존 생성기의 `_build_*` 인라인 코드를 **그대로 이동**(재작성 금지).
2. 생성기는 파이프라인 반환값(또는 캐시)만 읽는다. 생성기의 `from collectors import …` 5곳 제거.
3. build.py 디스패치·registry.py·워크플로는 무변경(회귀 0).

완료 기준: `grep "from collectors" generators/` 결과 pipelines.py 1곳. → 달성, §10 참조.

### Phase C — 컬렉터 내부 결합 절단 (위반 1-3 해소) — **Phase B에 흡수돼 종료**

FRED SERIES 목록·enabled 여부를 `get_macro()`가 번들에 실어 보내면서 목적이 달성됐다(§10).
캐시 envelope 메타로 내려보내는 원안보다 단순하고, 생성기의 컬렉터 상수 import는 0이 됐다.
stock·financials·ta는 애초에 컬렉터 상수를 템플릿에 노출하지 않아 대상이 아니었다.

### Phase D — 경량 프로바이더 계약 (스펙 DATA PROVIDER ABSTRACTION)

인터페이스 클래스 계층은 **만들지 않는다**(현 규모에 과설계). 대신:

1. 도메인별 "컬렉터 반환 계약"을 모듈 docstring + validator로 고정한다 — 이미 사실상 존재
   (market: `{code: {price, prev, as_of, source}}`). 계약 문서화가 곧 추상화다.
2. 프로바이더 교체 = 같은 계약을 지키는 컬렉터 모듈 교체. market_collector의
   Yahoo→Frankfurter→ExchangeRate-API 폴백이 이 패턴의 실증이다.
3. 새 소스 추가 시 규칙: 기존 컬렉터 수정이 아니라 **같은 계약의 새 모듈** + 파이프라인에서 병합.

### Phase E — 미비 도메인 (§5 결정 반영 후)

events(수집원 확정 시)·goal(asset envelope에 편입) — §5 결정에 종속되므로 마지막.

## 4. 2-모듈 규칙 점검

스펙: "신규 기능이 기존 모듈 2개 초과 수정을 요구하면 중단·재고". Phase A~C는 각각
utils(신설)+repositories / pipelines+generators / collectors+generators로 **2개 이내 수정**을
지킨다. Phase 간 의존은 A→B→C 순차이며 각 Phase 단독으로도 가치가 있다(부분 중단 가능).

## 5. 결정 사항 (2026-07-28 확정 — 구현은 이 표를 따른다)

| # | 쟁점 | 스펙 | **확정** |
|---|---|---|---|
| 1 | 갱신 주기 | 12h(00:00/12:00) | **하이브리드** — news·market은 현행 고빈도 유지(30분), macro·stock·financials·asset은 12h(00:00/12:00 KST)로 통일. 스펙의 12h를 기본값으로, 신선도가 본질인 2개 도메인만 명시적 예외 |
| 2 | 백엔드 DB | Notion | **TH_DATA vault 유지** — Notion 미도입. 07-27 확정 스키마가 단일 소스 |
| 3 | 테마 | 하드코딩 전면 금지 | **하이브리드 유지** — 테마 *선정*은 뉴스 빈도·키워드(자동), 테마→종목 *표시 매핑*만 `config/themes.py` 수기 큐레이션(전종목 자동 분류 오탐 회피) |
| 4 | 이벤트 | 수집 | **출처 명기 수기 + FRED 자동 병행** — 공식 무료 API 부재 일정(FOMC 등)은 출처 URL·확인일을 적은 수기 데이터를 검증된 사실로 간주. FRED `next_release` 자동분을 우선 표시 |
| 5 | Goal | 독립 도메인 모듈 | **asset envelope에 `goal` 필드로 편입** — 자산 합계의 파생값이라 독립 수집원이 없음. 모듈 신설 안 함 |

### 5-1. 결정 1의 구현 함의 — **cron 변경 불필요**(실측 확인)

결정 직후 현행 cron을 전수 확인한 결과, **이미 하이브리드 계약을 만족하고 있어 바꿀 파일이
없다**. 기계적으로 "macro·stock·financials → 12h"를 적용하면 오히려 퇴행한다:

| 워크플로 | 현행 cron | 성격 | 판정 |
|---|---|---|---|
| news.yml | `*/30 * * * *` (30분) | 뉴스 = 고빈도 대상 | 유지 |
| macro.yml | `0 * * * *` (60분) | design/25로 **시세 스트립**(환율·금리·원자재)이 편입돼 시세 도메인이 됨 | 유지 |
| stock.yml | KR 장중 매시 + KR/US 마감 | 장중 랭킹 = 시세 | 유지 |
| financials.yml | `0 21 * * *` (일1회) | 분기 공시 주기 | 유지 — **12h로 바꾸면 빈도가 2배로 늘어난다**(12h < 24h). 스펙의 12h는 상한이지 하한이 아니다 |
| morning.yml | `30 21 * * 0-4` (일1회) | 페이지 없는 데이터/대시보드 갱신 스텝 | 유지 |
| trades.yml | push 트리거 | 이벤트 구동 | 유지 |

즉 결정 1의 실질 산출물은 코드 변경이 아니라 **계약 명문화**다: 스펙의 12시간은 "느린
도메인의 갱신 상한"이며, 시세성 도메인(news·market·macro strip·stock)은 명시적 예외다.

## 6. 부수 작업 — 화면 결함 3건 (2026-07-29 구현 완료)

아키텍처 감사와 별개로 사용자가 보고한 화면 문제를 함께 처리했다. 셋 다 "확보된 사실만
정직하게 보여준다"는 기존 원칙의 적용 실패였다.

### 6-1. 모닝리포트 아카이브 삭제 (깨진 링크)

대시보드 Hero의 「리포트 전문 보기」가 `docs/morning/YYYY-MM-DD/`로 연결됐는데, 그 페이지들은
v1 셸 상속물이라 ① Phase 9에서 은퇴한 `style.css`·`app.js`에 의존하고 ② nav가 구 5링크
(대시보드/모닝리포트/뉴스/매매일지/AI Office)를 가리켜 현행 정보구조와 어긋났다. 내용은
Dashboard·News가 전부 커버하므로 아카이브를 **삭제**했다.

제거 대상: `docs/morning/`(아카이브 전체 + index), `docs/static/css/style.css`,
`docs/static/js/app.js`(소스에서 이미 은퇴한 v1 자산의 잔존 배포본),
`generators/morning/generate.py::list_dates()`, 대시보드 컨텍스트의 `latest_morning`과 버튼.
`generators/morning/`은 페이지를 쓰지 않는 데이터 스텝으로 계속 남는다(캐시 소비처 유지).
`generators/base.py::copy_static`의 "아카이브가 v1 자산을 참조하므로 rmtree 금지" 근거는
소멸했으나, 발행물 사고 폭을 줄이려 삭제 없는 복사는 그대로 둔다.

### 6-2. Macro 페이지 재구성 — "세계가 어떻게 돌아가는가"

기존 구성은 비트코인이 span-6 카드로 최상단을 차지해, 단타 도구가 거시 화면의 주역이 되어
있었다. 카드 순서를 우선순위로 재정의했다.

```
금융시장 (span-12)          ← 신설. 환율·달러 / 금리·변동성 / 원자재 3그룹 + 코인 1줄
한국은행 기준금리 (span-12)
경제지표 FRED (span-12)
경제일정 (span-12)
```

- **코인은 한 줄**로 격하했다(`build_crypto_line`) — 원화·달러 시세와 김치 프리미엄만.
- 각 타일에 **미니차트**(3개월 일봉 스파크라인)를 붙였다. 선 색은 첫 값 대비 마지막 값 방향
  (`--market-up/down/flat`)이라 등락 배지와 어긋나지 않는다.
- 신규 심볼 4종을 유니버스에 추가했다(스펙 MARKET 도메인 목록 완성): 브렌트유(`BZ=F`),
  은(`SI=F`), 미30년물(`^TYX`), 러셀2000(`^RUT`).
- 신규 모듈 `collectors/history_collector.py`(배치 일봉 수집)와 `utils/sparkline.py`
  (ta_repository에서 일반화해 분리 — TA와 Macro가 공유). 이력 수집이 실패해도 스팟 타일은
  그대로 나온다(미니차트만 생략) — 두 소스의 실패가 서로를 무너뜨리지 않게 하는 분리다.

실측(2026-07-29 로컬 빌드): 15타일 전부 값·등락·스파크라인 정상 렌더, 김치 프리미엄 -0.28%.

### 6-3. FRED/ECOS 키 미설정 — 코드 문제 아님

`FRED_API_KEY`·`ECOS_API_KEY`가 `.env`에도 `.env.example`에도 없었고, GitHub Secrets에도
등록되지 않은 것으로 보인다(발행된 페이지가 "미설정" 안내를 표시 중). 수집기는 설계대로
가짜 값을 만들지 않고 사실대로 결측 처리하고 있으므로 **코드 결함이 아니라 설정 누락**이다.

조치: `.env.example`에 두 키를 발급 URL과 함께 추가하고, **GitHub Secrets에도 등록해야 한다**는
점을 명시했다(Macro 페이지는 CI가 발행하므로 `.env`만으로는 해결되지 않는다 — 자산 키들과
정반대 성격이라 혼동하기 쉬운 지점이다). 화면 안내 문구에도 발급처와 등록 위치를 넣었다.
**남은 작업은 사용자의 키 발급·등록뿐이다.**

## 7. Phase A 구현 — 캐시 계약 (macro 파일럿, 2026-07-29 완료)

결정 3건(2026-07-29): ① 캐시 물리 위치 = **발행물을 캐시로 간주**(별도 파일 없음)
② 폴백 = **항목별 폴백 + 나이 상한** ③ 범위 = **macro 파일럿 → 확산**.

### 7-1. 결정 ①의 근거 — 루트 `cache/`는 CI에서 존재하지 않는다

`.gitignore`가 `/cache/`를 제외하므로 GitHub Actions는 매 실행을 빈 캐시로 시작한다. 거기에
도메인 캐시를 두면 last-good 보호가 **CI에서만 조용히 작동하지 않는다** — 정확히 보호가 필요한
환경에서만 없는 셈이다. 별도 캐시를 커밋하면 같은 데이터가 두 벌 남고 cron마다 커밋이 두 배가
된다(docs/data 기준 약 440KB). 그래서 이미 커밋되는 발행물을 직전 상태로 읽는다.

캐시 계층은 물리적 사본이 아니라 `utils/domain_cache.py`의 load/save 계약으로 존재한다.
스펙이 그린 "캐시와 발행물의 물리적 분리"는 포기하되, 그 분리의 실익(수집 실패로부터 발행물
보호, 쓰기 경로 단일화)은 전부 얻는다.

### 7-2. 폴백 규칙

`merge_last_good(new, previous, max_age_h)` — 이번에 결측(None)인 키만 직전 값으로 채운다.

- 새 값이 있으면 **항상 새 값이 이긴다**. 이 모듈은 결측을 메울 뿐 값을 판정하지 않는다
  (판정은 validators 책임 — 규칙이 두 곳으로 갈라지면 안 된다).
- 폴백된 항목은 **원래 `as_of`를 유지**한다 → 신선도 배지가 나이를 정직하게 드러낸다.
- 나이 상한(기본 7일) 초과 또는 시각 불명이면 폴백하지 않는다(낡은 값보다 빈칸).
- **전량 결측이면 저장 자체를 건너뛴다** — 빈 파일로 덮으면 직전 발행물까지 잃는다.

선례: `market_collector`의 `market_last.json`(26h 상한)이 같은 방식으로 이미 검증됐다.

### 7-3. 파일럿이 드러낸 결함 2건 (둘 다 수정)

실제로 돌려보지 않았으면 못 찾았을 것들이다.

1. **폴백이 데이터까지만 도달하고 화면에서 막혔다.** macro 템플릿이 경제지표 카드를
   `fred_enabled`(=API 키 설정 여부)로 분기하고 있어서, 직전 발행물에서 되살아난 지표가
   있어도 "FRED_API_KEY 미설정" 안내가 카드를 덮었다. 분기 기준을 **실제 확보된 지표 유무**
   (`has_fred`, 생성기가 계산)로 바꿨다. 키 미설정 안내는 데이터가 하나도 없을 때만 뜬다.
2. **되살아난 항목이 페이지 전체 렌더를 죽였다.** 폴백은 과거 발행물의 항목을 되살리므로
   그 시절 스키마에 지금 템플릿이 참조하는 키가 없을 수 있다. 그 경우 Jinja 접근 결과가
   `Undefined`인데, `Undefined`는 `is not none` 검사를 통과해 숫자 필터로 흘러들어
   `UndefinedError`로 페이지를 통째로 날린다(실측 확인). `generators/base.py`에 `_missing()`을
   두어 숫자 표시 필터 6종이 `None`과 `Undefined`를 같게 취급하도록 했다.

### 7-4. 확산 전 확인 사항

macro를 실제 cron으로 1~2일 돌려본 뒤 stock·ta·financials로 확산한다. 확산 시 각 도메인의
발행물이 **키-항목 매핑**인지 먼저 확인할 것 — `save_keyed`는 그 형태를 전제한다.
`calendar.json`처럼 이벤트 목록인 발행물은 대상이 아니다(FOMC 수기 일정이 항상 채워져
전량 결측이 구조적으로 불가능하다).

## 8. 자산 결함 3건 (2026-07-29 실계좌 검증 완료)

### 8-1. 한국투자 위탁 — 외화예수금이 통째로 빠져 있었다

**증상:** 계좌 현황이 실제와 맞지 않음.

**원인(실측):** 위탁 잔고 TR(`TTTS3012R`)의 `output2`에는 **예수금 필드가 아예 없다**.
실제 응답 키셋은 `frcr_pchs_amt1·ovrs_rlzt_pfls_amt·ovrs_tot_pfls·rlzt_erng_rt·
tot_evlu_pfls_amt·tot_pftrt·frcr_buy_amt_smtl1/2·ovrs_rlzt_pfls_amt2` — 전부 손익 계열이다.
기존 코드의 `deposit_usd = _pick_float(summary, "frcr_dncl_amt_2", ...)`는 그래서 **항상 None**
이었고, 계좌 총액은 주식 평가액만이었다.

**측정된 크기:** 외화예수금이 계좌 총액의 **14.8%** — 딱 그만큼 적게 표시되고 있었다.

**조치:** 체결기준현재잔고 TR(`CTRP6504R`)을 추가 호출해 `output2`(통화별)에서 외화예수금을
가져온다. 계좌 총액 = 주식평가액 + 외화예수금으로 명시 합산한다.

**쓰지 않기로 한 것:** `output3.tot_asst_amt`(총자산금액)는 실측에서 (주식+외화예수금)×환율의
**1.53배**가 나왔다. 이 위탁 계좌 범위 밖 자산까지 포함하는 값으로 보이며, 그대로 총액으로
쓰면 없는 돈을 만들어낸다. 검증된 두 값을 직접 더하는 편이 안전하다.

**오해였던 것:** 거래소 코드 `NASD`가 나스닥만 조회한다고 의심했으나, 실측에서 `NASD`는
미국 전체를 돌려준다(NVDA+SOC 2종목 = `CTRP6504R` 전체 조회 결과와 일치, 비율 1.0000).
누락 없음 — 이건 원인이 아니었다.

### 8-2. 키움 손익률 −1718%

**원인:** `opw00018`의 `총수익률` 필드를 그대로 %로 사용했다. KOA가 이 값을 100배 스케일로
돌려준다(−1718 = −17.18%).

**조치:** 스케일 규칙을 추측해 나누지 않는다. **이미 확보한 절대금액에서 직접 계산**한다 —
계좌는 `총평가손익금액 / 총매입금액`, 종목은 `평가손익 / (매입가 × 보유수량)`. 두 금액은
화면의 다른 곳에서도 쓰이므로 이미 검증된 값이고, 소스가 스케일을 바꿔도 옳다.
보고된 값은 교차검증용으로만 쓴다 — 배율이 0.5~2배 범위를 벗어나면 로그로 남기되 화면은
계산값을 따른다. 원가를 어떤 경로로도 못 구하면 **결측**으로 둔다(스케일 미검증 값을
내보내느니 손익률 행을 생략).

검증: 한투 위탁에서 우리 계산 −2.63% = KIS 보고 −2.63% (완전 일치).

부수 조치: `collectors/kiwoom_desktop/account.py`가 잔고 summary 원시값을 로그에 남긴다.
이 결함을 로그 없이 추적할 수 없었다 — 시세·주문 수집기는 이미 같은 raw 로그를 남기고
있었고 그게 과거 버그를 잡은 방법이었다.

### 8-3. 예수금 / 주식 평가액 분리

4계좌 전부 다음 계약으로 통일했다.

| 필드 | 뜻 |
|---|---|
| `securities_krw` / `securities_usd` | 유가증권(주식·ETF) 평가금액 |
| `deposit_krw` / `deposit_usd` | 예수금(현금) |
| `balance_krw` | 계좌 총액 = 유가증권 + 예수금 |

키움은 `총평가금액`이 예수금을 포함하는지 KOA 문서로 확정할 수 없어서 **보유종목 평가금액
합계와 대조해 런타임에 판정**한다(`_deposit_looks_included`). 추측 대신 확보한 데이터로
판정하므로 소스가 바뀌어도 조용히 틀리지 않는다.

원가 역산의 기준은 항상 **유가증권 평가액**이다 — 예수금 포함 총액에서 역산하면 원가가
부풀어 손익률이 실제보다 작게 나온다.

화면(`static/js/asset.js` `breakdownHtml`)에 「주식 평가액 / 예수금」 2행을 추가했다.
둘 다 결측이면 블록 자체를 렌더하지 않는다. BYBIT은 예수금 개념이 없어 대상이 아니다.

## 9. Macro 그래프 가시성 (2026-07-29)

「그래프 가시성이 너무 떨어진다 / 한눈에 보이게」에 대한 조치. 브라우저에서 실측한 문제와
수정 후 수치는 아래와 같다.

| 항목 | 이전 | 이후 |
|---|---|---|
| 차트 크기 | 147×40px | 149×48px(가로형 배치) |
| 봉 개수 / 밀도 | 60봉, **봉당 2.4px** | 22봉(1개월), **봉당 6.8px** |
| 기준선·면적 | 없음 | 구간 첫 값 점선 + 방향색 면적(opacity 0.14) |
| 크기 정보 | 없음(진폭이 정규화됨) | 일간 + 1개월 등락률 병기 |
| 카드 높이 | 1131px(한 화면 초과) | **659px(1280×800에 들어감)** |
| 타일 | 세로형 265×173, 4열 | 가로형 352×82, 그룹 3열 |
| 반복 노이즈 | 같은 시각 15회 반복 | 카드 헤더에 1회 |

핵심은 두 가지다.

1. **밀도.** 60봉을 147px에 욱여넣으면 봉당 2.4px라 선이 뭉개진다. 창을 1개월로 줄이고 타일을
   가로형으로 바꿔 봉당 6.8px를 확보했다. 수집은 3개월 그대로 두어 나중에 창을 넓힐 수 있다.
2. **정규화의 거짓말.** 스파크라인은 min/max 정규화라 **모든 계열이 같은 진폭으로** 그려진다 —
   환율 0.1% 움직임과 천연가스 30% 급등이 똑같이 보였다. 기준선을 그어 방향을 즉시 읽히게 하고,
   크기는 숫자(일간·1개월 등락률)로 병기했다. design/00 R4("색·모양만으로 정보를 전달하지
   않는다")의 연장이다.

「한눈에」는 그룹 3개를 세로로 쌓지 않고 **3열로 나란히** 두어 달성했다 — 15개 지표가 한 화면에
들어온다. 좁은 화면에서는 `auto-fit minmax(300px,1fr)`로 1열이 되며 가로 스크롤은 없다(실측).
선 대비는 카드 배경 대비 5.77:1로 WCAG AA 그래픽 기준(3:1)을 넘는다.

## 10. Phase B 구현 — 도메인 파이프라인 추출 (2026-07-29 완료)

**DoD 달성:** `grep "from collectors" generators/` 결과가 `pipelines.py` 한 곳뿐이다.

이동한 것(재작성 아님 — 동작을 바꾸지 않는 것이 이 단계의 목적이다):

| 신규 파이프라인 | 흡수한 생성기 코드 | 생성기 줄 수 |
|---|---|---|
| `get_macro()` | `_build_fred/_build_ecos/_build_upbit/_build_history` + 지표·일정·스트립 조립·발행 | 93 → 31 |
| `get_ta()` | `_build_preview` | 45 → 35 |
| `get_stock()` | KR/US 랭킹 수집·검증, 유니버스 확정, 보조시세, Hub 발행 | 90 → 48 |
| `get_financials()` | `_universe/_close_price/_build_kr/_build_us` | 85 → 34 |
| `get_news_counters()` | news_v2의 `news_collector.collect()` 직접 호출 | — |
| `get_asset_raw()` | 4계좌 수집(Kiwoom 공유 세션 처리 포함) | 108 → 62 |

설계 판단 2가지:

- **반환은 dict(번들)다.** 튜플이면 항목이 늘 때마다 모든 호출부가 깨지고, 생성기가 위치로
  값을 꺼내야 해서 읽기 어렵다.
- **`get_stock()`이 유니버스 확정까지 가져간다.** 보조 시세 조회(`collect_quotes`)가 유니버스에
  의존하므로, 수집 호출을 생성기에 남기지 않으려면 그 선행 계산도 이 계층이 가져야 한다.

`get_macro()`가 `fred_labels/fred_series/fred_enabled`를 실어 보내므로 **macro 한정으로 Phase C
(컬렉터 내부 결합 절단)도 함께 달성**됐다. stock·financials·ta는 애초에 컬렉터 상수를 템플릿에
노출하지 않아 Phase C 대상이 아니다 — 즉 Phase C는 사실상 종료다.

**회귀 검증:** 리팩터 후 재발행한 `docs/{stock,financials,ta}/index.html`을 커밋본과 diff한 결과
변경은 전부 데이터(시세·날짜·유니버스 정렬)뿐이고 구조 변화는 0이다. 테스트 324개 통과.

## 11. 하지 않는 것

- 디렉터리 대개편·전면 재작성(스펙 명시 금지).
- Normalizers 물리 계층 신설 — repositories의 to_*()가 이미 그 역할.
- 프로바이더 인터페이스 클래스 계층 — 계약 문서화 + validator로 대체(§3-D).
- 잘 작동하는 morning/news 파이프라인 수정(라이브 무간섭 원칙, design/20).
