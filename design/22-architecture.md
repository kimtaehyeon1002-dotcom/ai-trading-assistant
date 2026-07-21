# 22. 기술 아키텍처 설계

본 문서는 신규 10페이지 체제의 **코드 구조·정보 구조**를 확정한다. Phase별 순서·완료기준은 로드맵 문서(20), Envelope 필드·신선도 T 실측표·암호화 KDF 파라미터는 데이터 요구 문서(21)가 단일 진실 소스이며 여기서는 참조로 처리한다. 신선도 **상태 모델**은 00 디자인 시스템이 확정한 4상태(FRESH/DELAYED/STALE/CLOSED-SNAPSHOT)를 정본으로 채택한다(§5-2). 이 문서 단독으로도 읽히도록 핵심 계약은 요약 재기술한다.

계좌 구성은 **4계좌로 확정**한다: ① 키움증권(단타·스윙 매매 주력) ② 한국투자 위탁(미국주식 전용, USD/KRW 듀얼 표시) ③ 한국투자 ISA(ETF 전용, 절세) ④ BYBIT(암호화폐). KB증권 계좌는 삭제되었으며, 이에 따라 수기 입력 경로가 설계에서 완전히 사라진다 — 자산 파이프라인은 **전량 API 자동 수집**이다(§7-1). 08(Asset)·09(Portfolio) 문서는 이미 4계좌 기준으로 개정 완료되어 본 문서와 정합한다.

전략 골격은 **strangler fig(공존형 교체)**다. 현행 `templates/base.html`(2블록 셸)·`static/css/style.css`(단일 다크 토큰 13개)·`static/js/app.js`(35줄 필터)는 **동결**하고, 옆에 v2 셸·토큰·모듈을 신설해 페이지를 하나씩 이관한 뒤 마지막에 v1을 은퇴시킨다. 파이프라인(collectors→validators→repositories→calculators→generators)은 견고하므로 손대지 않는다.

## 0. 검증된 현행 앵커 사실

아래는 실제 파일 확인 결과이며, 설계의 전제다.

| 파일 | 확인된 사실 | 설계 함의 |
|---|---|---|
| `templates/base.html` | 블록 `title`·`content` 2개뿐, nav 5링크 하드코딩, `<html data-theme="dark">`이나 CSS가 참조 안 함, `root` 상대경로 주입 | 셸 블록 체계·데이터주도 nav·테마 훅 전부 신설 |
| `templates/_macros.html` | 매크로 5개(`pctbadge`/`quote_row`/`quote_table`/`news_item`/`stat_card`), morning은 자체 `market_rows` 중복 정의 | v2 컴포넌트 라이브러리로 통합 |
| `static/css/style.css` | `:root` 변수 13개(다크 직결), 팔레트 밖 하드코딩 hex 선택자 13곳(`.tag-*`·`.badge-*`·`.imp-*`·`.status-*`·`.note`·`.chip.active`) | 토큰 레이어 재구축 + hex 회수 |
| `static/js/app.js` | 35줄 IIFE, 외부 라이브러리 0, "빌드 렌더 + display 토글" 2개, fetch·localStorage·검색 전무 | 모듈 분리·신규 작성 |
| `build.py` | `TARGETS` 5튜플 + `run_build` if 분기, 공통 마무리(dashboard+static+office) 항상 실행 | 레지스트리 디스패치로 재설계 |
| `generators/base.py` | Jinja2 Env 1개, 필터 5종(`pct`/`signclass`/`price`/`money`/`kst`), `render()`·`copy_static()` | 그대로 재사용, 필터만 증분 추가 |
| `.gitignore` | 루트 `/cache/`만 제외, `data/` 하위는 커밋 허용 구조(주석으로 `data/cache/` 커밋 의도 명시) | `data/snapshots/` 명시 제외 추가가 필수(§7-2) |

---

## 1. 목표 파일 트리

코드가 아니라 **파일 배치와 역할**만 정의한다. 신설(＋)·변경(~)·동결(=)을 표기한다.

### 1-1. templates/

```
templates/
  = base.html              (v1 셸 — 동결, Phase 9에서 제거)
  = _macros.html           (v1 매크로 — 동결)
  = dashboard.html morning.html morning_index.html news.html trades.html ai_office.html  (v1, 순차 이관)
  + base_v2.html           (신규 셸: 사이드바240+헤더64, 신규 블록 체계)
  + _macros_v2/            (v2 컴포넌트 라이브러리 — 파일 분할)
  +   card.html            (카드 등급 Hero/Standard/Compact/Row 매크로)
  +   freshness.html       (신선도·세션 배지, as-of 캡션 매크로)
  +   quote.html           (시세 행/타일 — v1 중복 market_rows 흡수)
  +   panel.html           (Stock Hub 패널 골격, panel_slot에 주입)
  +   nav.html             (사이드바·헤더 — config/nav 컨텍스트 소비)
  +   chart.html           (인라인 SVG 스파크라인·미니바·라인차트 매크로)
  +   forms.html           (탭바·필터칩·세그먼트·검색 입력 골격)
  + pages/                 (v2 페이지 본문 — base_v2 상속)
  +   ta.html macro.html stock.html financials.html asset.html portfolio.html settings.html
  +   dashboard_v2.html news_v2.html
```

역할: `base_v2`는 셸 단일 소스, `_macros_v2/`는 페이지가 색·간격·신선도 규칙을 재발명하지 못하게 막는 **컴포넌트 계약의 물리적 위치**다. 카드 등급 타이포 위계(Hero 32px→Standard 24px→Compact/Row 16px)와 신선도 배지 4상태는 매크로 시그니처로 강제된다.

### 1-2. static/

```
static/
  = css/style.css          (v1 — 동결)
  = js/app.js              (v1 — 동결)
  + css/tokens.css         (원시 팔레트 → 시맨틱 토큰 레이어)
  + css/base_v2.css        (셸·레이아웃·그리드 12컬럼)
  + css/components.css     (카드/배지/탭/칩/패널/차트 컴포넌트 스타일)
  + js/boot.js             (FOUC 방지 인라인 부트 + 초기 상태 적용)
  + js/store.js            (local/sessionStorage 래퍼 — 설정 단일 접근점)
  + js/freshness.js        (신선도·세션 판정 단일 모듈 — 시계 보정 포함)
  + js/updown.js           (등락색 모드 전환)
  + js/tabs.js             (탭/세그먼트/필터 — data-속성 기반)
  + js/search.js           (검색 인덱스 로더 + 커맨드 팔레트)
  + js/hub.js              (Stock Hub 전역 패널 — 상세 JSON + 경량 시세 JSON 조합)
  + js/gate.js             (Asset/Portfolio WebCrypto 복호화 게이트)
```

CSS는 `@import` 대신 **로드 순서 계약**(tokens → base_v2 → components)으로 캐스케이드를 통제한다. JS는 IIFE 모듈을 페이지가 필요한 것만 `scripts` 블록으로 선택 로드한다(전 페이지 전량 로드 금지).

### 1-3. generators/ · config/

```
generators/
  = base.py pipelines.py    (Env·필터·기존 파이프라인 — 재사용, 증분만)
  ~ base.py                 (필터 추가: freshness_attr, tv_symbol, band 등 표시 보조)
  + registry.py             (타깃→생성기 레지스트리 — build.py가 소비)
  + ta/ macro/ stock/ financials/ asset/ portfolio/ settings/  (신규 생성기)
config/
  = markets.py feeds.py keywords.py settings.py
  ~ markets.py              (시세 유니버스 심볼 증분 — KOSPI/VIX/DXY/금리 등)
  + nav.py                  (사이드바·헤더 메뉴 단일 소스)
  + calendar.py            (세션·휴장 달력)
  + universe.py themes.py entities.py  (종목 유니버스/테마 매핑/종목명→티커)
```

계층 규칙은 불변이다. 신규 생성기도 데이터는 pipelines/repositories/calculators에서만 취득한다.

---

## 2. URL / 정보 구조 설계

전 페이지 "디렉터리 + index.html + `root` 상대경로" 방식을 유지한다(GitHub Pages `/Th_bot/` 프리픽스에서 무설정 동작). 절대경로·`<base>` 미도입.

### 2-1. 10페이지 경로

| 페이지 | 발행 경로 | nav 노출 | 셸 | 데이터 JSON |
|---|---|---|---|---|
| Dashboard | `docs/index.html` | ○ | v2 | (인라인 렌더 중심) |
| Macroeconomics | `docs/macro/index.html` | ○ | v2 | `docs/data/macro/*.json` |
| News | `docs/news/index.html` + `docs/news/YYYY-MM-DD/` | ○ | v2 | 인라인 + 아카이브 |
| Stock | `docs/stock/index.html` | ○ | v2 | `docs/data/stock/rankings.json` + `docs/data/stock/quotes.json` |
| Financial Statements | `docs/financials/index.html` | ○ | v2 | `docs/data/financials/{티커}.json` |
| Technical Analysis | `docs/ta/index.html` | ○(Coming Soon) | v2 | `docs/data/ta/preview.json` |
| Stock Hub | (전용 페이지 없음 — 전역 패널) | × | `panel_slot` | `docs/data/stock/hub/{시장}_{티커}.json`(상세, 일 1회) + `docs/data/stock/quotes.json`(시세, 장중 공유) |
| Asset | `docs/asset/index.html` | ○(잠금) | v2 | `docs/data/assets.enc.json` |
| Portfolio | `docs/portfolio/index.html` | ○(잠금) | v2 | `docs/data/assets.enc.json`(공유) |
| Settings | `docs/settings/index.html` | ○(하단) | v2 | `docs/data/meta/freshness.json` |

Stock Hub는 페이지가 아니라 어느 페이지에서든 열리는 오버레이이므로 URL은 **해시 딥링크**(`#hub=KRX:005930`)로만 존재한다. Stock Hub의 데이터는 **시세(quotes)와 상세(hub)를 파일·주기 모두 분리**한다 — 장중 갱신은 유니버스 전 종목 현재가·등락을 담은 `quotes.json` 1파일에 국한하고, 종목별 `hub/{시장}_{티커}.json`(일정·뉴스 매칭·딥링크 등 상세)은 일 1회(마감 후)만 재발행한다(분리 근거와 주기는 §8-2·§9-1).

### 2-2. 기존 URL 처리(전수 보존)

상세 매트릭스는 로드맵 문서. 원칙만:

- `docs/morning/YYYY-MM-DD/`·`docs/morning/index.html`: **영구 보존.** Dashboard+News가 콘텐츠를 커버한 뒤에도 아카이브 URL은 200을 유지한다. 06:30 워크플로는 가동 유지하되 신규 발행 중단 여부만 로드맵에서 판단.
- `docs/trades/`: Portfolio 흡수 시 `meta-refresh` 안내 페이지로 전환(하드 삭제 금지). 최종 거취는 Phase 9 확정.
- `docs/ai-office/` + `runlog.json`: **runlog는 `docs/data/meta/freshness.json`의 생성 원료**로 계속 발행하되, Settings ④(데이터 갱신 안내)의 fetch 소스는 **freshness.json 단일**로 확정한다(runlog 직접 fetch 금지 — 소스 이원화 방지). freshness.json은 build.py 공통 마무리 단계에서 매 빌드 발행한다(§6). 페이지 거취는 Phase 9 확정.
- 기존 dated URL 전수 200 유지가 Phase 9 완료기준의 하나다.

### 2-3. 클라이언트 fetch 대상 규약

CI는 `git add docs`만 수행한다(확인된 사실). 따라서 **브라우저가 fetch하는 JSON은 반드시 `docs/data/**`**에 둔다. 소급 불가 원장 중 **커밋 가능한 것은 전일 랭킹·PER 밴드 축적뿐**이며 이때만 `data/**` 커밋 채널을 쓰고, 워크플로의 `git add` 범위 확장 결정이 선행된다(§8). **자산 스냅샷 원장은 커밋 채널이 아니다** — 로컬 전용(.gitignore)이며 발행물은 암호문 `assets.enc.json` 단독이다(§7-1, 데이터 요구 문서 §9-4가 단일 진실). 재조회 가능한 시계열은 매 빌드 재조회하여 `docs/data/`로만 발행한다(누적 금지).

---

## 3. 디자인 시스템 매핑 전략

00 문서의 토큰명을 CSS 변수로 옮기는 **명명 규칙과 파일 구성**만 정의한다(값 나열은 00이 소스).

### 3-1. 2계층 변수 명명 규칙

- **원시 팔레트(private)**: `--p-teal-400`, `--p-slate-500`처럼 색 이름 기반. 컴포넌트가 직접 참조 금지.
- **시맨틱 토큰(public)**: 00의 점 표기(`surface.card`)를 하이픈으로 사상 → `--surface-card`, `--text-primary`, `--brand-primary`, `--market-up`, `--chart-series-1`, `--border-default` 등. 컴포넌트는 시맨틱만 참조한다.
- 매핑 규칙: **점→하이픈, 그룹 접두어 유지**. `market.up-bg`→`--market-up-bg`. 이 규칙이 있어야 00 개정 시 기계적 대조가 가능하다.

### 3-2. 파일 구성과 캐스케이드

`tokens.css` 한 파일에 (a) 원시 팔레트 (b) 시맨틱 매핑 (c) 스코프 오버라이드 슬롯을 순서대로 둔다. 스코프는 셀렉터로 분리한다:

- 등락색 모드: `[data-updown="kr"]`(기본)·`[data-updown="global"]` 스코프에서 `--market-up`/`--market-down`만 재바인딩. `signclass` 필터가 부여하는 `.up/.down` 클래스는 **무수정**(색은 변수 교체로만 전환 — 확인된 재사용 가능 지점).
- 신선도색: **FRESH/DELAYED/STALE/CLOSED-SNAPSHOT 4상태**(00 확정 모델, §5-2)를 상태 토큰(`--status-warning` 등)에 매핑, 배지 컴포넌트가 소비. 상태별 판정 문턱은 데이터 요구 문서 §6 실측표가 정본이다.

### 3-3. 토큰 스코프 결정 — 다크 우선, 라이트만 유예 (C-3) — 본 절이 정본

**결정: 다크 테마·한국 등락색을 실값으로 채우고, `[data-updown]` 글로벌 등락색은 처음부터 두 스코프 모두 값을 채우며, 라이트 테마만 "스위칭 슬롯 확보"로 유예한다.**

근거: 00 문서 자체가 "다크 테마 단일 운영(라이트 없음)"을 명시했고, 라이트 팔레트는 요구 확정 전 과설계다(1인 운영 현실성). 반면 등락 글로벌 모드는 Settings ①(등락 색상 모드 토글)이 약속한 필수 사용자 가치이므로 유예 대상이 아니다 — 글로벌 값을 채우는 시점이 없으면 Settings 토글이 동작 불능이 된다. 따라서 `[data-updown="kr"]`·`[data-updown="global"]` 두 스코프는 **tokens.css 구축 시점(로드맵 Phase 1)에 즉시 실값을 채우고**, `updown.js` 모듈 구현은 로드맵의 담당 Phase에 명시 배정한다(Settings Phase 이전 완료가 조건). 라이트는 `:root[data-theme="light"]` 셀렉터만 비워 두어, 훗날 값만 채우면 컴포넌트 수정 없이 활성화된다. 즉 **글로벌 등락색=즉시 지원, 라이트 테마=슬롯 예약**의 비대칭 처리이며, 이 결정이 정본이고 로드맵의 스코프아웃·Phase 문구는 여기에 정렬한다.

### 3-4. 하드코딩 hex 회수 + R6 린트

현행 style.css의 팔레트 밖 하드코딩 hex 선택자 13곳(`.tag-*`·`.badge-*`·`.imp-*`·`.status-*`·`.note`·`.chip.active` — 확인)은 v2 이관 시 전량 시맨틱 토큰으로 회수한다. 00 R6(색 신설 시 전체 헥스 대조)은 **빌드 타임 린트 게이트**로 구현: 팔레트 정의부 밖에서 `#[0-9a-f]{3,6}` 매칭 0건을 Phase 1 완료기준으로 삼는다(grep으로 검증 가능). 이는 "하나의 헥스가 등락·상태·차트에 동시 배정되는 결함"을 색상표 레벨에서 차단한다.

---

## 4. 템플릿 상속·매크로 설계

### 4-1. base_v2 블록 체계 (C-1)

`base_v2.html`은 v1의 `title`/`content` 2블록을 다음으로 확장한다:

| 블록 | 용도 | 비고 |
|---|---|---|
| `title` | `<title>` | v1과 동일 |
| `head_extra` | 페이지 전용 `<link>`/메타/프리로드 | 검색·재무 JSON preload 등 |
| `content` | 본문 | 12컬럼 그리드 컨테이너 내부 |
| `panel_slot` | Stock Hub 전역 패널 마운트 지점 | 전 페이지 공통, 비어 있어도 존재 |
| `scripts` | 페이지가 필요한 JS 모듈만 선택 로드 | 전량 로드 금지 |

셸 구조는 사이드바 240px(접힘 64px) + 헤더 64px + 콘텐츠(최대 1600px, 12컬럼/거터 24px). 헤더에 듀얼 시계·글로벌 검색·세션 인디케이터 마운트 포인트를 둔다. `boot.js`용 인라인 부트 스니펫은 `<head>` 최상단에 두어 FOUC(테마·등락모드·마스킹 초기 상태 깜빡임)를 방지한다.

### 4-2. config/nav.py 단일소스 계약 (C-2)

nav 하드코딩(현행 base.html 5링크)이 페이지 추가마다 셸 수정을 강제하는 문제를 제거한다. `nav.py`가 메뉴 목록(라벨·경로·아이콘·그룹·잠금 여부·`active` 키)을 단일 정의하고, **v1·v2 두 셸이 같은 컨텍스트를 소비**한다(공존 기간 드리프트 방지). 생성기는 `active` 키만 넘기고 링크 렌더는 `nav.html` 매크로가 nav 컨텍스트를 순회해 수행한다. 잠금 그룹(Asset/Portfolio)은 nav 데이터의 `locked` 플래그로 자물쇠 표기를 파생한다.

### 4-3. 컴포넌트(매크로) 재사용 단위

`_macros_v2/`의 단위와 계약:

- **카드**(`card.html`): 등급(Hero/Standard/Compact/Row)을 인자로 받아 타이포 위계(00 §8-2 카드 등급 체계·§3-2 타입 스케일)를 강제. 헤더에 타임스탬프 슬롯이 **필수**(N1: as-of 없는 시세 렌더 금지)라 매크로 시그니처에서 as-of를 요구한다.
- **신선도 배지**(`freshness.html`): 값과 `data-asof`/`data-session`/`data-ttl` 속성을 함께 출력. 판정 텍스트는 빌드가 아니라 `freshness.js`가 열람 시점에 채운다(§5-2). 배지 상태는 4상태 전부를 표현 가능해야 한다.
- **시세/스택바/차트**: 등락색은 클래스만, 스택바는 00 §8-5 전역 계약(`chart.series-1~5` 고정 배정 + 라벨 병기)을 상속. 스파크라인은 빌드 타임 인라인 SVG.
- **패널**(`panel.html`): Stock Hub 골격(A~E 블록)만 렌더, 값은 `hub.js`가 fetch로 채움(시세 B블록은 `quotes.json`, 상세 C~E는 종목별 hub JSON — §5-6).

morning의 중복 `market_rows`는 `quote.html`로 단일화(v1 은퇴 시 자연 소멸).

### 4-4. 공존 종료 기준 (C-1)

전 페이지가 `base_v2` 참조로 확인되면 `base.html`·`style.css`·`app.js`를 제거한다. 완료기준(눈으로 검증 가능): **v1 셸 참조 grep 0건**, 전 페이지 단일 토큰 시스템, 기존 dated URL 전수 200. 이는 Phase 9 게이트다.

---

## 5. 클라이언트 JS 설계

전 모듈은 외부 라이브러리 0, IIFE, `store.js`를 상태 단일 접근점으로 공유한다. 현행 "빌드 렌더 + data-속성 토글" 패턴을 계승·확장한다.

### 5-1. boot.js (FOUC 방지)

`<head>`에서 동기 실행. `store.js`가 읽는 localStorage 값(테마·등락모드·마스킹 기본값·모션 줄이기)을 `<html>`의 `data-*` 속성으로 즉시 반영해 첫 페인트부터 올바른 색으로 그린다. 나머지 모듈은 `defer`.

### 5-2. freshness.js — 신선도/세션 단일 모듈 (C-5)

**상태 모델 정본**: 00 §9-2가 확정한 **4상태 — FRESH / DELAYED / STALE / CLOSED-SNAPSHOT**를 그대로 채택한다(상태 수·시각 표현 불변). 판정 문턱은 00 원형(T·3T)에 GitHub Actions cron 실측 지연(§8-2)을 반영해 **FRESH 상한 = 2T**로 명시 확정한다 — "cron 유예를 어느 구간에 반영하는가"의 모호성을 이 한 문장으로 종결하며, 행별 T·문턱 실측값은 데이터 요구 문서(21) §6 실측표(DELAYED 열 포함)가 수치의 단일 진실 소스다. 본 모듈은 그 값을 기계적으로 소비한다.

**입력→출력 계약**: DOM에서 `[data-asof]`(UTC ISO)·`[data-ttl]`(소스별 기대 주기 T, 초)·`[data-session]`(유효 세션 키)을 읽어, 보정된 열람 시점 시계와 비교해 배지·명도를 출력한다.

흐름:
1. **시계 보정**: 정적 사이트라 서버 시각 API는 없으나, 페이지(또는 임의 fetch) 응답의 **HTTP Date 헤더**와 클라이언트 시계의 편차를 1회 측정한다. 편차가 임계(5분) 초과면 판정 기준 시각에 편차를 보정 적용하고, 보정 불가 상황(헤더 부재 등)이면 **"기기 시계 확인" 안내 배지**를 표시한다. 이 1단계가 없으면 기기 시계가 틀어진 환경(모바일·해외 시간대 오설정)에서 FRESH↔STALE 오판이 발생해 "정직한 신선도"라는 핵심 가치가 클라이언트 환경에 좌우된다.
2. `as_of` 파싱 → 경과 = 보정된 now − as_of.
3. 세션 판정: `config/calendar` 파생 규칙(빌드가 data-속성/부속 JSON으로 심음) + 현재 시각으로 장전/장중/장후/야간/휴장 산출. **세션 마감 후는 CLOSED-SNAPSHOT이 경과 시간 판정보다 우선**한다(세션 우선 원칙).
4. 신선도 판정(4상태 단일 규칙): **경과 ≤ 2T = FRESH**, **2T < 경과 ≤ STALE 문턱 = DELAYED**(문턱 기본값 3T, 행별 실측값은 데이터 요구 문서 §6-2), **문턱 초과 = STALE**. DELAYED가 FRESH 상한과 STALE 문턱 사이 전 구간을 정의상 커버하므로 무명 구간(예: 시세 60~90분, 뉴스 속보 45~90분)은 구조적으로 발생하지 않는다. STALE은 값을 `--text-secondary`로 강등, CLOSED-SNAPSHOT은 "MM/DD 마감 기준" 라벨 부여·라이브 점 금지(S2/S4).
5. 상대시각 1분 주기 갱신, 세션 경계 도달 시 상태 전환을 값 갱신보다 우선(S4).

헤더 듀얼 시계·세션 점·카드 배지가 **동일 함수**를 참조한다(00 §7-3/§9-4 요구). 야간선물은 상태 A(LIVE) 미지원, CLOSED-SNAPSHOT/STALE 2상태만 운용(Kiwoom 수동 제약).

### 5-3. updown.js — 등락색 모드 전환

Settings 토글/헤더 사용자 메뉴가 호출. `<html data-updown>`을 `kr`↔`global`로 바꾸고 `store.js`에 저장. CSS 변수만 재바인딩되므로 DOM 재렌더·필터 수정 불필요(§3-2 — 두 스코프의 실값은 Phase 1에 이미 채워져 있다, §3-3). 차트 캔들·스파크라인 색도 같은 변수를 참조해 일괄 전환.

### 5-4. tabs.js — 탭/세그먼트/필터

News 4탭·Stock 테마·매매 분류 등 공통. 전 행을 빌드 렌더한 뒤 `data-tab`/`data-level`/`data-cat`로 display 토글(현행 패턴). 탭 상태는 URL 해시/쿼리로 전달(딥링크·뒤로가기 보존). 밀도·정렬 토글 상태는 `store.js`.

### 5-5. search.js — 글로벌 검색

`docs/data/search-index.json`(이름·티커·거래소·경량 미리보기)을 지연 로드. `Ctrl/⌘+K`로 커맨드 팔레트(Level 2 오버레이) 오픈, 그룹 3종(종목/뉴스/페이지). ↑↓ 탐색·Enter 이동·Esc 닫기. 종목 선택 시 Stock Hub 패널을 연다(전용 페이지 이동 아님). search-index는 일 1회(마감 후) 재발행이므로(§8-2) 장중 diff에 기여하지 않는다.

### 5-6. hub.js — Stock Hub 전역 패널

흐름: 트리거(검색 결과·종목 행·Portfolio 종목) 클릭 → 해시 `#hub=시장:티커` 세팅 → **2파일 fetch 조합**: ① `docs/data/stock/quotes.json`(유니버스 일괄 경량 시세 — 현재가·등락, 장중 갱신) ② `docs/data/stock/hub/{시장}_{티커}.json`(상세 C~E: 일정·뉴스 매칭·딥링크, 일 1회 갱신) → `panel.html` 골격에 A~E 블록 주입(시세 B블록은 ①에서, 상세는 ②에서) → 열기(우측 슬라이드, 포커스 트랩, Esc/스크림 클릭 닫힘). 두 파일의 as-of가 다르므로 **블록별 as-of를 각각 표기**하고 신선도 판정도 블록 단위로 `freshness.js`를 재사용한다. quotes.json은 랭킹·Stock 페이지와 공유되므로 패널 오픈 시 이미 캐시돼 있을 확률이 높다. 유니버스 밖 종목은 빈 상태(05 §2-5). 딥링크 진입 시 로드 즉시 패널 오픈.

이 시세/상세 분리는 §9-1(발행 파일 설계)·§9-3(diff 관리)의 전제다 — 시세가 박힌 종목별 hub 파일을 장중 매회 재발행하면 일 수천 파일-리비전이 쌓이는 문제를 파일 구조 차원에서 차단한다.

### 5-7. store.js — 설정 저장 경계

localStorage: 등락모드·테마·시계 구성·마스킹 기본값·관심 테마·모션 줄이기(기기 귀속·저민감). sessionStorage: 게이트 세션·마스킹 현재 상태·아코디언·유휴 타이머 기준. **경계 명시**: 클라이언트 설정은 CI에 없으므로 빌드 타임 가중치(예: 관심 테마의 News 정렬)에 반영 불가 → 클라이언트 재정렬로만 처리(설계 문서에 한계 명기).

---

## 6. build.py 레지스트리 디스패치 (C-4)

현행 `TARGETS` 5튜플 + if 분기(확인)는 10페이지에서 유지 불가하다. **타깃→생성기 레지스트리**로 재설계한다:

- `generators/registry.py`가 `{타깃명: (생성기 진입점, 소속 그룹, all 포함 여부)}`를 선언. `build.py`는 레지스트리를 순회 디스패치(if 나열 제거).
- `all`의 범위 재정의: 현행 `all`=morning+news+trades 3개 의미(확인) → 레지스트리의 "정기 발행" 플래그 집합으로 재정의. 무거운 stock/financials는 별도 타깃 그룹으로 분리해 `all`이 매번 종목 전량을 재빌드하지 않게 한다. stock 그룹 내부도 **장중 타깃(rankings+quotes)**과 **마감 후 타깃(hub 상세+search-index)**을 별개 타깃으로 등록해 주기 분리(§8-2)를 레지스트리 레벨에서 표현한다.
- 공통 마무리(dashboard·`copy_static`·office)는 레지스트리와 무관하게 유지하되, dashboard가 v2로 치환되면 진입점만 교체. **`docs/data/meta/freshness.json` 발행을 공통 마무리 단계에 추가**한다 — 어떤 타깃이 실행되든 매 빌드 갱신되어 Settings ④의 단일 소스가 된다(runlog는 그 생성 원료, §2-2).
- **회귀 0 완료기준**(검증 가능): 재설계 후 `build.py all`이 v1 6페이지를 **바이트 동일** 재생성, 기존 5타깃 CLI 동작 보존, pytest 그린. 이는 Phase 1 게이트다.

---

## 7. Asset / Portfolio 게이트·암호화 아키텍처 (C-6)

정책은 **A(passphrase 파생키 클라이언트 암호화) + D(상대값만 평문 공개)** 조합. KDF 파라미터·마스킹 범위는 데이터 요구 문서가 소스, 여기서는 코드 구조 흐름만.

### 7-1. 데이터 흐름 — 4계좌 전량 API 수집

수집 대상은 4계좌이며 **수동 입력 경로는 존재하지 않는다**(KB증권 계좌 삭제로 수기 입력 UI·검증 분기·주1회 사람 병목이 설계에서 제거됨). 계좌별 수집 경로와 화면 요구:

| 계좌 | 역할 | 수집 경로 | 파생·표시 요구 |
|---|---|---|---|
| 키움증권 | 단타·스윙 매매 주력 | 키움 잔고 TR(로컬 32-bit 데스크톱) | 매매일지 연동, 회전율 높음 → 일 갱신 필수 |
| 한국투자 위탁 | 미국주식 전용 | KIS REST | **USD/KRW 듀얼 표시 필수** — 적용환율 필드 포함, 환율민감도 파생 |
| 한국투자 ISA | ETF 전용(절세) | KIS REST(위탁과 동일 API, 계좌번호 분리) | ETF 보유·절세 한도 관점 필드 |
| BYBIT | 암호화폐 | Bybit REST | 24시간 시장 — 세션 개념 없음, as-of 명시 필수 |

```
[데스크톱 app/sync.py 확장]
  키움잔고TR(로컬) + KIS REST(위탁·ISA 2계좌) + Bybit REST   ← 4계좌 전량 API, 수동 입력 없음
      → data/snapshots/ 1일 1행 append (로컬 전용, .gitignore — 커밋 금지)
      → 파생계산(전일대비·90일추이·비중·환율민감도·위탁 USD/KRW 듀얼)
      → passphrase 기반 KDF → AES-GCM 암호화
      → docs/data/assets.enc.json  (발행물은 암호문 단독 — 90일 히스토리도 payload 내부)
[CI]  자격증명·평문 절대 미보유 — enc.json 그대로 배포
[브라우저]  gate.js: passphrase 입력 → WebCrypto 복호화 → 렌더
```

- **평문 원장은 로컬 전용**: `data/snapshots/`는 .gitignore 대상이며 어떤 채널로도 커밋하지 않는다(데이터 요구 문서 §4·§9-4가 단일 진실). 공개 리포에 평문 자산 원장이 한 번이라도 커밋되면 git 히스토리 삭제 불가 특성상 영구 사고이고 A+D 암호화 체계 전체가 무효가 된다. 90일 추이 히스토리는 암호문 payload 내부에 담아 발행한다.
- **실패 폴백 단일 경로**: 수기 입력 대체 경로가 없으므로 폴백은 하나다 — **API 수집 실패 시 직전 스냅샷 유지 + STALE 표시**. 계좌별 부분 실패도 동일(실패 계좌만 직전 값+STALE, 성공 계좌는 갱신). 자산 신선도는 수기/자동 이원화(24h/7일)가 필요 없어져 **T=24h 단일 규칙**으로 단순화된다(실측값은 데이터 요구 문서 §6-2).
- **복호화 성공 = 인증**: 게이트는 별도 비밀번호 해시를 저장하지 않는다(복호화 자체가 인증). 따라서 Settings ③의 "비밀번호 변경"은 클라이언트만으로 완결 불가 — **데스크톱 재암호화·재커밋**이 실제 변경 경로다(Settings 문서 정정 사항).
- **게이트 밖 평문(D)**: 절대금액·역산 가능 값(목표금액·투입원금 포함)은 게이트 밖 어디에도 두지 않는다. 공개 뷰는 상대값(%·비중·달성률)만. Dashboard의 현행 자산 평문 렌더(`templates/dashboard.html` 36~88행 `erp` 블록 — 총 자산·목표 절대금액·현금흐름 금액)는 **Phase 4에서 선차단**한다.
- Settings "4자 이상" 정책은 오프라인 무차별 대입 저항을 위해 긴 passphrase 정책으로 개정(문서 정정).

### 7-2. pre-commit 평문 가드 (C-6)

정적·공개 리포에서 클라이언트 게이트는 접근 제어가 아니다(JSON 직접 열람·git 히스토리 영구). 따라서 방어선은 **평문이 커밋되지 않게 하는 것**이며, 수집이 전량 자동화된 지금 가드도 자동 산출물 기준으로 구성한다:

- **.gitignore에 `data/snapshots/` 명시 추가가 선행 필수**: 현행 .gitignore는 루트 `/cache/`만 제외하고 `data/` 하위 커밋을 허용하는 구조로 확인되었다(주석으로 `data/cache/` 커밋 의도 명시). 명시적 제외 없이는 스냅샷이 실제로 커밋된다.
- pre-commit 훅 + CI 검사 2중 가드: ① `data/snapshots/` 경로의 스테이징 유입 자체를 차단(경로 패턴 매칭) ② `docs/`(및 게이트 밖 전 산출물)에서 절대금액·역산값 패턴을 grep, 매칭 시 커밋/빌드 실패.
- 완료기준(검증 가능): 게이트 밖 절대값·역산값 grep 0건 + `data/snapshots/` 추적 파일 0건(Phase 4·8 게이트).

---

## 8. JSON 발행 채널 · 워크플로 (C-6/C-7)

### 8-1. 발행 채널 규약

| 채널 | 커밋 여부 | 용도 | git add |
|---|---|---|---|
| `docs/data/**` | ○(CI) | 브라우저 fetch 대상, 재조회 가능 데이터(암호문 enc.json 포함) | 현행 `git add docs` |
| `data/**` | ○(데스크톱 or 확장) | 소급 불가 원장 — **전일 랭킹 히스토리·PER 밴드에 한정** | **`git add docs data` 확장 결정 선행** |
| `data/snapshots/` | **×(.gitignore — 커밋 금지)** | 자산 평문 스냅샷 원장(로컬 전용, §7-1) | — (pre-commit 가드로 유입 차단, §7-2) |
| `cache/**` | ×(.gitignore) | CI 재생성 산출물 | — |

핵심: fetch 대상이 `cache/`에 있으면 CI에서 사라진다. 히스토리 원장 중 커밋 가능한 것은 전일 랭킹·PER 밴드뿐이며, 커밋 폭증을 감안해 재조회 가능 시계열은 `docs/data/`로만 발행(누적 금지). 자산 스냅샷은 채널 표에서 별도 행으로 분리해 **커밋 금지를 규약 수준으로 명시**한다.

### 8-2. reusable workflow + cron 시차 (C-7)

현행 3개 yml(morning·news·trades)은 setup·env·commit 블록이 복붙이고 Notion DB ID가 3중 하드코딩(확인). reusable workflow(또는 composite action)로 공통화하고 각 워크플로는 트리거·빌드 타깃·커밋 메시지만 주입한다. cron 시차 배치(경합·rate limit 완화):

| 워크플로 | 주기(제안) | 발행 대상·비고 |
|---|---|---|
| morning | 평일 06:30 KST(기존) | 가동 유지, 신규 발행 판단은 로드맵 |
| news | 30분(기존) | 실측 지연 20분~3.7h → FRESH 짧고 STALE 정직 노출 |
| macro | 60분 | Phase 6 신설, API키 env 주입 |
| stock(장중) | KR 장중 30~60분 | **rankings.json + quotes.json(경량 시세 1파일)만 갱신** — hub 상세·search-index 미발행. "장중 20분"은 미보장 → T 하향 |
| stock(마감 후) | KR 마감 후 1회 + 미 마감 후 1회 | **hub 상세(`hub/{시장}_{티커}.json` C~E) + search-index.json 재발행** — 일 1회 주기로 분리 |
| trades | push 트리거(기존) | 데스크톱 push 경유 |

stock 워크플로의 **장중/마감 후 발행 대상 분리**가 핵심이다: 시세를 포함한 종목별 hub 파일(일 100~200파일)을 장중 매회 재발행하면 장중 7~13회 × 200파일 = 일 수천 파일-리비전이 공개 리포 히스토리에 쌓여 §9-3이 우려한 저장소 비대화를 스스로 재현한다. 장중 diff를 rankings+quotes 2파일로 한정하면 이 문제가 발행 설계 차원에서 사라진다(§9-1·§5-6과 동일 계약).

공통 개선: `pages-commit` concurrency 그룹 유지(직렬화), setup-python pip 캐시 추가, CI에 pytest 단계 추가, Notion DB ID 단일 소스화. cron은 GitHub 지연을 전제로 신선도 T를 실측 기반 보수 설정(FRESH ≤ 2T 유예)한다 — 상세는 데이터 요구 문서.

---

## 9. 성능·용량 고려

### 9-1. JSON 크기·분할 — 시세/상세 분리 원칙

- **종목별 분할 + 시세 분리**: Stock Hub·재무 통합 파일은 수 MB로 비대해지므로 `hub/{시장}_{티커}.json`·`financials/{티커}.json`으로 분할한다. 단, **종목별 hub 파일에는 시세 블록(B)을 넣지 않는다** — 현재가·등락은 유니버스 일괄 `quotes.json` 1파일에만 담아 장중 갱신하고, hub 파일은 상세(C~E)만 담아 일 1회 갱신한다(§5-6·§8-2). 유니버스=TOP30×2 ∪ 테마 종목 ∪ Notion watchlist(일 100~200종목)로 한정, 밖은 빈 상태.
- **경량 인덱스 분리**: `search-index.json`은 이름·티커·거래소·미리보기만(검색 첫 타이핑 반응성). 상세는 종목 클릭 시 개별 fetch. 재발행은 일 1회(마감 후)로 hub 상세와 동일 주기.
- **시계열 재조회**: 스파크라인·30일 차트·경제지표 추이는 매 빌드 소스 API 재조회로 채우고 스냅샷만 발행(누적 저장소 신설 회피).

### 9-2. 페이지 로드 예산

- 빌드 타임 렌더 유지가 기본: HTML에 값이 이미 있어 초기 표시에 fetch 불필요. fetch는 Stock Hub·랭킹·검색 등 **온디맨드/전역 데이터에 한정**.
- 인라인 SVG 스파크라인은 96×28 단색 종가선 수준으로 수십 바이트 규모. 외부 차트 라이브러리 미도입(CSP·용량 이점).
- 모듈 선택 로드(§4-1 `scripts` 블록)로 페이지별 JS 페이로드 최소화. News의 전 기사+펼침 렌더는 일 30~40건이면 문제없고, 초과분은 날짜 아카이브(`docs/news/YYYY-MM-DD/`)로 분리.

### 9-3. 커밋 diff 관리

30~60분 주기 × 페이지 증가는 자동커밋 비중(현행 약 57%)을 키운다. 완화 3축:

1. **변동을 데이터 파일로 국한**: HTML 골격은 안정 유지하고 변동은 `docs/data/**` JSON에 모은다.
2. **변경 없는 타깃 스킵**: 정기 재빌드가 전 HTML을 재작성하지 않도록 레지스트리에서 판단(diff 없을 때 커밋 생략은 현행 워크플로 패턴 계승). 단 **이 스킵은 시세가 박힌 파일에는 무효**다 — 시세는 매회 바뀌므로 항상 diff가 발생한다.
3. **시세 파일 최소화(구조적 해법)**: 따라서 시세를 담는 파일 수 자체를 줄이는 §9-1의 시세/상세 분리가 실질 완화책이다. 장중 diff는 rankings.json + quotes.json 2파일로 수렴하고, 종목별 hub 파일·search-index는 일 1회만 바뀐다.

이 절충은 "빌드 타임 렌더" 원칙과 "diff 최소화" 사이의 명시적 트레이드오프이며, 값-JSON 분리 렌더의 도입 범위는 페이지별로 판단한다.

---

**문서 끝. 본 문서는 00 디자인 시스템의 토큰명·수치·신선도 4상태 모델을 변경 없이 인용하며, Phase 순서·완료기준·URL 보존 매트릭스는 로드맵 문서(20), Envelope·신선도 T 실측표(DELAYED 문턱 포함)·KDF 파라미터·자산 스냅샷 커밋 금지 규정은 데이터 요구 문서(21)를 단일 소스로 참조한다. 계좌는 키움·한투 위탁·한투 ISA·BYBIT 4종이 확정본이다.**
