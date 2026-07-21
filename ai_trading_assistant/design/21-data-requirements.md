# 21. 데이터 요구 명세

신규 10페이지가 소비하는 **모든 데이터의 계약서**다. "화면은 값 + 기준시각 + 신선도 + 세션 4종 메타의 소비층"이라는 이 사이트의 본질(로드맵 §2)을 데이터 관점에서 못 박는다. 페이지별 상세 격차·와이어프레임은 각 design 문서를, 셸/토큰/워크플로 구현 계약은 `22-architecture.md`(예정)를, Phase 순서·게이트는 `20-implementation-roadmap.md`를 참조한다. 이 문서 단독으로도 "무엇을 어디서 받아 어떤 파일로 발행하고 어떻게 신선도를 판정하는가"를 결정할 수 있게 작성한다.

## 0. 표기 규약

- **신규 여부**: `기존`(현행 그대로 재사용) · `부분`(필드·구조 보강 필요) · `신규`(수집·저장 계층 전량 신설).
- **발행 채널**: `docs/data/**`(클라이언트 fetch 대상, CI `git add docs`) vs `data/**`(소급 불가 히스토리 원장, 데스크톱/CI 커밋). §7 참조.
- **갱신 주기**: 설계가 요구하는 T이며, GitHub cron 실측 지연(20분~3.7h)상 보장이 아니라 **목표치**다. 실제 신선도는 §6의 열람 시점 판정으로 정직하게 강등한다.
- **계좌 구성(확정, 4계좌)**: ① 키움증권 — 단타·스윙 매매 주력 ② 한국투자 위탁 — 미국주식 전용(USD/KRW 듀얼 표시) ③ 한국투자 ISA — ETF 전용(절세·만기 관리) ④ BYBIT — 암호화폐. **KB증권 계좌는 삭제**되었으며, 본 문서의 자산 데이터 요구·수집기·신선도 규칙은 전부 이 4계좌 + 전량 자동 수집 기준이다(design/08·09 개정과 정합).
- 현행 코드 진술은 전부 파일 확인 사실이다(`models/market.py`, `config/markets.py`, `collectors/market_collector.py`, `validators/market_validator.py` 등).

---

## 1. Envelope 표준 규격 (Phase 0 계약)

전 페이지가 공유하는 단일 값 봉투. 야간선물 신선도 3중 방어(현행 `market_validator._fresh`·`NIGHT_FUTURES_MAX_AGE_H=60`)를 페이지별 복제 없이 공통 계층으로 승격하기 위한 기반이다.

### 1-1. 필드 정의

| 필드 | 타입 | 필수 | 의미 |
|---|---|---|---|
| `value` | number \| null | ✔ | 대표값(가격·지수·수익률 등). 결측은 반드시 `null`(가짜 0 금지) |
| `change_abs` | number \| null | ✔ | 절대 등락폭. Hero "+32.14", 금리 bp 표기용. 현행 미보유(§1-3) |
| `change_pct` | number \| null | ✔ | 등락률(%). 소스가 전일값 미제공 시 `null` |
| `unit` | string | ✔ | `"pt"`,`"KRW"`,`"USD"`,`"%"`,`"bp"`,`"x"` 등 |
| `as_of_iso` | string(UTC ISO8601) | ✔ | 데이터 기준시각. **클라이언트 신선도 판정의 입력** |
| `source` | string | ✔ | 출처 식별자(`"yahoo"`,`"frankfurter"`,`"fred"`,`"ecos"`,`"upbit"`,`"kiwoom"`,`"kis"`,`"bybit"`,`"dart"`,`"edgar"`,`"manual"`). **`"manual"`은 거시 예상치 수기 YAML(§2-2) 전용** — 자산 수집은 4계좌 전량 자동(§3)이므로 자산용 수기 소스 경로는 존재하지 않는다 |
| `session_key` | string | ✔ | `"kr_regular"`,`"kr_night"`,`"us_regular"`,`"globex"`,`"fx"`,`"crypto_24h"`,`"none"` |
| `expected_T_min` | integer | ✔ | 소스별 기대 갱신 주기(분). §6 실측표 값 |
| `freshness_basis` | string | ✔ | `"as_of"`(기준시각 기준) \| `"collected_at"`(수집시각 기준, 뉴스) |
| `ref_price` | number \| null | · | 기준가(야간선물·CLOSED-SNAPSHOT 등락률 산출 근거). 병기 캡션용 |
| `label` | string | · | 표시 라벨(다국어·소스 라벨) |

### 1-2. JSON Schema (`schema/envelope.schema.json`)

데이터 계약 문서로서 Phase 0 산출물. 구현 코드가 아니라 검증 스키마다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "envelope.schema.json",
  "type": "object",
  "required": ["value","change_abs","change_pct","unit","as_of_iso","source","session_key","expected_T_min","freshness_basis"],
  "properties": {
    "value":          {"type": ["number","null"]},
    "change_abs":     {"type": ["number","null"]},
    "change_pct":     {"type": ["number","null"]},
    "unit":           {"type": "string"},
    "as_of_iso":      {"type": "string", "format": "date-time"},
    "source":         {"type": "string"},
    "session_key":    {"enum": ["kr_regular","kr_night","us_regular","globex","fx","crypto_24h","none"]},
    "expected_T_min": {"type": "integer", "minimum": 1},
    "freshness_basis":{"enum": ["as_of","collected_at"]},
    "ref_price":      {"type": ["number","null"]},
    "label":          {"type": "string"}
  },
  "additionalProperties": false
}
```

**완료기준(Phase 0)**: `market.json`이 이 스키마를 통과, 전 항목 `as_of_iso`·`session_key` non-null, 기존 야간선물 60h·flat 차단 테스트가 일반화 규칙 위에서 그대로 그린.

### 1-3. Quote 모델 확장 (하위호환)

현행 `Quote`(models/market.py)는 `symbol,name,price,change_pct,currency,source,as_of`만 보유하며 `as_of`는 **KST 표시 문자열**이다(`models/market.py` 확인). 현행 Quote에는 `from_dict`가 없고 캐시 재수화는 dict `.get` 직접 접근이다(`validators/market_validator.py`·`repositories/market_repository.py` 확인 — `NewsArticle`·`Trade`만 `from_dict` 보유). 봉투 계약을 위해 아래를 추가하되, 신·구 캐시 판독 경로 모두 `.get` 기본값 방식을 유지해 옛 캐시를 깨지 않게 한다.

| 추가 필드 | 근거 |
|---|---|
| `as_of_iso: str \| None` | 클라이언트 시계 비교용 UTC ISO. 기존 `as_of`(KST 표시)는 캡션용으로 유지 |
| `change_abs: float \| None` | `market_collector._yahoo`가 계산에만 쓰고 버리는 `previous_close`를 살려 `value - prev`로 산출 |
| `session_key: str` | 세션 판정기 입력 |
| `ref_price: float \| None` | 기준가 병기(야간선물·마감 스냅샷) |

---

## 2. 페이지 × 컴포넌트별 데이터 매핑

각 표: 요구 데이터 / 핵심 필드 / 소스 / 갱신 주기 / 현행 커버리지 / 신규 여부. 세부 필드 전량은 해당 design 문서 참조.

### 2-1. Dashboard (`/`) — design/01

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 커버리지 | 신규 |
|---|---|---|---|---|---|
| Hero 해석 문장 | 문장, 생성시각, 신선도 | 템플릿 조립 + Notion "오늘의 요약" 수기(옵션) | 1일1회 | 없음 | 신규 |
| 미국 지수 3종 | value·change_abs·%·as_of | yahoo `^GSPC/^IXIC/^DJI` | 마감 스냅샷 | 지수 수집 중, change_abs 부재 | 부분 |
| 한국 지수 카드 4타일 | KOSPI/KOSDAQ 현물·K200야간·USDKRW + 스파크라인 | yahoo `^KS11/^KQ11`·kiwoom·frankfurter | 장중 배치 | 현물·스파크라인 없음 | 부분 |
| 미국 카드 4타일 | S&P·NASDAQ·DOW·VIX + NQ선물 푸터 | yahoo `^VIX/NQ=F` | 배치 | VIX·NQ 없음 | 부분 |
| 핵심 뉴스 5행 | 카테고리·시각·딥링크·"리포트 수록" 점 | 현행 news 저장소 | 30분 | 있음(딥링크 앵커=`NewsArticle.id`) | 부분 |
| 오늘 일정 7행 | 시각·이벤트·완료상태·★핵심 | 세션 룰(config) + Notion 일정 DB | 1일1회 | 세션 룰만 | 부분 |
| 세션 푸터(거래대금·상승하락수·시간외) | 세션 보조 수치 | KRX 무료 경로 부재 → 축소 | 세션별 | 없음 | 신규(축소) |

축소 확정: 거래대금·상승하락 종목수·시간외 단일가·외국인 수급은 무료 소스 부재 → 세션 라벨+카운트다운(클라이언트 계산)으로 대체. 자산 절대값은 이 페이지에서 **렌더 금지**(§9, Phase 4 선차단).

### 2-2. Macroeconomics (`/macro/`) — design/02

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| 미국시장/원자재 | S&P·NASDAQ·DOW·SOX·WTI·Gold·Copper·NatGas + 스파크라인 | yahoo(`GC=F/HG=F/NG=F` 추가) | 60분 | 4지수·WTI만 | 부분 |
| 환율 | USDKRW + 30일 라인 + JPY/EUR/CNY·DXY | frankfurter 기간조회 + yahoo `DX-Y.NYB` | 60분 | 현재가만, %·크로스·DXY 없음 | 부분 |
| 채권·금리 | 미 2Y/10Y/30Y·국고채 3Y/10Y·기준금리·한미차, bp 변화 | FRED `DGS2/10/30` + ECOS | 60분 | 없음 | 신규 |
| Bitcoin | BTC/USD 7일·BTC/KRW·김치프리미엄·24h 거래대금 | yahoo `BTC-USD` + Upbit | 30분 | 없음 | 신규 |
| 변동성 | VIX·MOVE·Fear&Greed(VKOSPI 보류) | yahoo `^VIX/^MOVE` + CNN JSON | 60분 | 없음 | 신규 |
| 경제지표 10행 | 발표치·이전치·추이6·다음발표일 (**예상치 옵션**) | FRED 원계열 + releases/dates | 24h | 없음 | 신규 |
| 경제일정 | 일시·중요도·실적캘린더·FOMC D-day | FRED + config(FOMC 연1회) + Notion | 24h | 없음 | 신규 |

축소 확정: **예상치/서프라이즈** 무료 소스 부재 → 수기 YAML 입력 시에만 열 표시, 미입력 시 열 생략(빈칸 렌더 금지). VKOSPI(KRX 크롤링 취약)·S&P Global PMI(유료)·동결확률(CME 스크래핑)은 제외. ISM은 대체 소스 확보 전 보류.

### 2-3. News (`/news/`) — design/03

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| 4탭 배타 분류 | `tab(us/kr/macro/breaking)`, 배타 우선순위 | 현행 6분류 매핑(`news_categories`) | 30분 | 6분류 중복 게재 | 부분 |
| 리스트 행 | title·summary·source·published·`level(L1~L3)`·`level_reason`·`impact_tags[]` | RSS + 규칙 판정 | 30분 | 기본 필드만, level·태그 없음 | 부분 |
| 게재 카운터 | 일별 `collected_total`/`published_total`·탭분해 | 일별 상태 파일(신규) | 30분 누적, 자정 리셋 | 실행당 runlog만 | 신규 |
| 행 펼침 | RSS 요약(최대 280자)·시장 반응·관련 종목 칩·원문 | 저장소 + `config/entities.py` | 스냅샷 | 요약 절단 있음, 티커 사전 없음 | 부분 |
| 모닝 브리핑 3불릿 | bullets[3]·counts{L3,L2,L1}·생성시각 | 실측 조합 템플릿 | 1일1회+갱신 | 원료(top7/themes)만 | 부분 |
| 시장 스냅 | 탭별 지표 4행(미10Y·DXY·금 등 최대 11종) | yahoo `^TNX` 등 | 60분(macro 빌드 재수집분) — **news 빌드는 기존 market.json 재사용** | 일부 | 부분 |
| 키워드 레이더 | keyword·count·역인덱스 | `themes.extract`(top_n 3→6) | 30분 | 있음 | 부분 |
| 경제 캘린더 | time·event·consensus·actual·status | FRED/ECOS(예상치 수기 옵션) | 1일1회+발표후 | 없음 | 신규 |
| `first_seen_at`/`batch_id` | 신규 도트·탭 배지 | 저장소 병합 시각 | 30분 | 없음 | 신규 |
| 날짜 아카이브 | `/news/YYYY-MM-DD/` | morning 일자 패턴 재사용 | 30분 | 단일 페이지 | 신규 |

확정: 상세 요약 "3줄"→"RSS 원문 최대 280자"로 완화(본문 미저장·no-AI·저작권). `AI BRIEFING`→`모닝 브리핑` 개칭(design v1.2 반영). 기사별 시장 반응은 1단계 생략, 우측 "시장 스냅" 카드로 대체. **news 30분 빌드는 시세를 재수집하지 않는다** — 시장 스냅의 값은 macro 빌드가 갱신한 market.json을 그대로 읽는다(§3 호출 예산·§5).

### 2-4. Stock (`/stock/`) — design/04

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| 테마 자금흐름 스트립 | 테마 6~8·합산 거래대금·평균 등락 | 랭킹 calculator | 장중 30~60분 | 없음 | 신규 |
| 테마 카드 ×6 | KR/US TOP5(확장 TOP10)·종목·현재가·%·거래대금 | `config/themes.py` + 시세 | KR 장중/US 마감 | 없음(키워드 사전만) | 신규 |
| TOP30 테이블 ×2 | 순위·종목·시장·대표테마·현재가·%·거래대금 (확장: 거래량·시총·스파크) | FDR/pykrx(KR) + yahoo 배치(US) | 배치 | 없음 | 신규 |
| 랭킹 변화(개선5) | 전일 순위 스냅샷 | 히스토리 원장 `data/` | 일1회 축적 | 없음 | 신규 |

확정: 미국 "전시장 TOP30" 무료 불가 → **유니버스 내 TOP30**으로 정의 변경, 캡션에 모집단 명시(§8). 확장 모드 "당일 스파크라인"→"최근 20일 일봉"으로 대체.

### 2-5. Stock Hub (전역 패널) — design/05

정적 사이트에서 트리거 가능한 **모든 종목의 JSON이 사전 존재**해야 한다. 유니버스 = TOP30×2 ∪ 테마 종목 ∪ Notion watchlist(§8).

| 블록 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| B 시세 개요 | 현재가·등락·세션·as_of + 스탯6(거래대금/거래량/시총/52주고저/PER) | KIS/yahoo `fast_info` | 시세 배치 | 없음 | 신규 |
| C 액션 허브 | TradingView 심볼(`KRX:005930`/`NASDAQ:NVDA`)·FS 딥링크 | 유니버스 config(시장 필드) | 정적 | 없음 | 신규 |
| D 다가오는 일정 | 유형·D-day·제목·목적지 URL | DART 공시 + EDGAR URL 조립 | 24h | 없음 | 신규(축소) |
| E 관련 뉴스 5건 | 제목·출처·시각·내부 링크 | 현행 news 저장소 + 종목 매칭 | 6h | 저장소 있음, 매칭 없음 | 부분 |

확정: 일정 5종 중 **한국 실적 예정·IR** 무료 소스 부재 → [공시=DART][실적=제출기한 역산 '추정' 캡션][SEC=EDGAR URL][배당=DART/yfinance] 4종으로 축소, IR 제외(design 05 D블록 정의 1줄 개정). PER 등 불안정 필드는 "값 없으면 셀 생략".

### 2-6. Financial Statements (`/financials/`) — design/06

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| 검색 자동완성 인덱스 | 이름·티커·현재가·% | `search-index.json` | 1일1회 | 없음 | 신규 |
| Hero 분기 실적 | 매출·영업이익·순이익 + YoY·5축 판정·룰 요약 | DART(KR)·EDGAR(US) | 분기 | 없음 | 신규 |
| 지표 카드 15장 | 성장·수익·안정·현금흐름(FCF 10년)·밸류(PER/PBR 5년밴드) + **업종평균 기준선** | DART/EDGAR + 자체 집계 | 분기(밸류만 주가기준) | 없음 | 신규 |
| 원본 아코디언 | 손익·재무상태·현금흐름표 5년, 계정 위계 | DART/EDGAR | 분기 | 없음 | 신규 |

확정: 업종평균 무료 소스 부재 → 유니버스 내 동일 테마 중앙값 자체 산출, 초기엔 **자사 5y 단독 판정**(design 06 §3-8 결측 플로우 그대로). PER/PBR 5년 밴드 소급 불가 → 주가 5년(FDR)÷분기 EPS로 근사, ⓘ 툴팁에 산출식 고지, 초기 분기 "밴드 산출 기간 부족" 캡션. FCF 10년은 EDGAR만 충족(yfinance 4년).

### 2-7. Technical Analysis (`/ta/`) — design/07

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| TA-PREVIEW | KOSPI 일봉 60일+·20일 이평·이격률·RSI(14)·60일 추세 | yahoo `^KS11`/FDR | 1일1회(T=24h) | 없음 | 신규 |
| HERO·SLOT·ROADMAP | 로드맵·변경로그·모듈 상태 | 정적 config | 빌드 | 없음(정적) | 신규(config) |

**Phase 2 수직 슬라이스 파일럿**. 그룹 내 최저 비용 → 계약·셸·토큰·클라 판정의 첫 실화면 검증 대상.

### 2-8. Asset (`/asset/`) — design/08

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| 자산 Hero | 총자산·전일대비·총수익·수익률·투입원금·90일 추이 | 데스크톱 `app/sync.py` + 스냅샷 원장(로컬 전용, §9-4) | 1일1회 | Notion assets(유형별 합계만) | 신규 |
| 목표 달성률 | 목표금액·현재·달성률·달성예상시점(파생) | Notion goals DB | 1일1회 | 있음(그대로 사용) | 기존 |
| 계좌 카드 ×4 | 잔액·전일대비·평가손익·비중·30일 스파크 + 계좌별 필수 필드(아래) | 키움 TR + KIS REST(위탁·ISA 2계좌) + Bybit v5 — **전량 자동 수집** | 1일1회 | 키움 실현손익·야간선물만 | 신규 |
| 자산 추이/통화노출 | 총자산 히스토리·환율 민감도(파생) | 스냅샷 원장 파생 | 1일1회 누적 | 없음 | 신규 |

계좌별 필수 필드(design 08 §3-4 카드 #3~#6, 사용 빈도순 키움 → 한투 ISA → 한투 위탁 → BYBIT과 정합):

- **키움증권(단타·스윙 주력)**: 잔액·전일대비 + 당일 실현손익 연동 필드(매매 빈도 최고 — trades 파이프라인과의 정합 확인 대상).
- **한국투자 ISA(ETF 전용·절세)**: 만기일(카드 캡션 "절세 · ETF 전용 · 만기 YYYY/MM")·납입한도 잔여. 통화는 KRW 단일.
- **한국투자 위탁(미국주식 전용)**: 합산 원화 + **USD/KRW 2행 분해 + 적용환율·기준시각 — 필수 필드(옵션 아님)**. 환율 표기 없는 환산값 렌더 금지(N1 확장, design 08 §2-4).
- **BYBIT(암호화폐)**: USDT 평가액 + 원화 환산. 24시간 시장이지만 발행은 스냅샷 → "수집 기준" 라벨 + "24시간 시장 · 스냅샷 값" 캡션 이중 차단(S2).

수기 입력 경로는 존재하지 않는다(KB 삭제로 소멸). 자산 신선도는 자동 수집 단일 규칙 T=24h(§6-2). **모든 값은 암호화 발행(§9)**. 게이트 밖 절대값·역산 가능 값 0건.

### 2-9. Portfolio (`/portfolio/`) — design/09

| 요구 데이터 | 핵심 필드 | 소스 | 갱신 | 현행 | 신규 |
|---|---|---|---|---|---|
| Hero 종합 | 전계좌 원화환산·일간/누적손익·**계좌 4행**·적용환율 | 데스크톱 잔고 TR + 시세 | 세션 인식 | 없음 | 신규 |
| 보유종목 테이블 | 종목·수량·매입단가·현재가·평가·수익률·비중 | 키움/KIS 잔고 + 시세 | 세션 인식 | 없음 | 신규 |
| 종목 상세 패널 | Stock Hub 상속 + 매입정보 | Hub JSON 재사용 | 종목별 | 없음 | 신규 |
| BYBIT 탭 | 코인 시세·라이브 점(24/7) | Bybit REST | 상시 | 없음 | 신규 |

확정: 국내 탭은 항상 CLOSED-SNAPSHOT 문법 고정("마감 복기"). 계좌 탭은 4계좌(키움/한투 위탁/한투 ISA/BYBIT) 고정 — 한투 위탁 탭은 USD/KRW 듀얼 + 적용환율 캡션 필수. BYBIT 라이브 점은 Bybit 공개 API CORS 확인 시에만. 예수금 D+2·주문가능은 잔고 TR 응답 범위. **암호화 발행(§9)**.

### 2-10. Settings (`/settings/`) — design/10

| 섹션 | 상태·데이터 | 저장 위치 | 신규 |
|---|---|---|---|
| ① 표시(등락색 한/글로벌·마스킹 기본·모션) | 클라이언트 상태 | localStorage | 신규 |
| ② 시계·시간대(12/24h·개장 카운트다운) | 상태 + KRX/US 세션 달력 | localStorage + `config/calendar` | 부분 |
| ③ 보안(비번·유휴 잠금) | 게이트 상태(복호화=인증, §9) | sessionStorage | 신규 |
| ④ 데이터 갱신 안내 | 소스별 T·마지막 생성·다음 예상·상태 | 빌드 메타 `docs/data/meta/freshness.json` | 부분(runlog 확장) |
| ⑤ 관심 테마(최대 10) | 칩 목록 | localStorage | 신규 |
| ⑥ 초기화 | 설정 리셋(비번·매매일지 제외) | — | 신규 |

확정: "4자 이상" 비밀번호 정책 → §9 KDF 정책에 맞춰 **긴 passphrase**로 개정. 관심 테마의 News 재정렬은 클라이언트 전용(빌드 타임 가중치 반영 불가 — CI에 설정 없음). ④의 단일 fetch 소스는 `freshness.json`이며 **runlog는 그 생성 원료**다(소스-원료 관계 고정) — 생성은 build.py 공통 마무리 단계에서 빌드마다 수행하고, 최초 구현은 Phase 2(freshness.js와 동시)로 배정한다(§4). ①의 등락색 글로벌 모드는 토글이 실제 동작해야 하므로 `[data-updown]` 글로벌 값은 초기 Phase부터 채워져 있어야 한다는 것을 데이터 요구로 명기한다(라이트 테마만 슬롯 예약 — 22-architecture §3-3 비대칭안과 정합).

---

## 3. 신규 수집기 명세

| 수집기 | 소스 | 무료 한도·제약 | 실패 시 폴백 | 담당 Phase |
|---|---|---|---|---|
| 시세 현재가(현물·지수·VIX·선물·원자재·BTC) | Yahoo Finance `fast_info` | 비공식 API — 클라우드(Actions) IP 대역 429/차단 빈발. Yahoo 심볼 5(현행 4지수+WTI)→20+. **호출 예산: macro.yml 60분·stock.yml 장중/마감 배치·morning 1회. news.yml 30분 빌드는 시세 호출 0회**(market.json 재사용, §4·§5) | 심볼별 `None` 강등(가짜0 금지), 직전 스냅샷 유지 | 3 |
| 시세 시계열(스파크라인·30일 history) | Yahoo Finance `history` | 현재가보다 호출 중량 큼 — 차단 리스크 최대 구간. **재조회는 macro.yml(60분)·stock.yml(마감 후)·morning에만 배정, news 빌드 재조회 금지** | 스파크라인 생략(§6-4), 직전 배열 유지 | 3 |
| 크로스환율 | Frankfurter(ECB) 기간조회 | 1일1회(CET 오후), 주말·공휴일 결측 | change_pct `null`, 주말 스냅샷 | 3 |
| 미 국채·경제지표 | FRED API(`DGS*`, `CPIAUCSL`, releases/dates) | 무료 키(env 주입), 1영업일 지연, **예상치 없음** | 지표 카드 생략, YoY 자체계산 | 6 |
| 국고채·기준금리 | 한국은행 ECOS Open API | 무료 키(env), 당일 반영 지연 | config 수기 병행(기준금리 저빈도) | 6 |
| BTC/KRW·거래대금 | Upbit 공개 API(무키·CORS) | 안정적 | 김치프리미엄 카드 생략 | 6 |
| Fear&Greed | CNN 비공식 JSON | UA 차단 사례 | 카드 생략(4열→3열 폴백) | 6 |
| 한국 랭킹·종목시세 | FinanceDataReader(현존 requirements) / pykrx | 공식 아님, 장중 20분 미보장(cron 병목) | 마감 EOD 스냅샷으로 축소 | 7 |
| DART 재무·공시 | DART OpenAPI | 무료 키, 일 ~2만 호출, 업종평균 미제공 | 유니버스 100~200 한정, 업종평균 결측 허용 | 7 |
| EDGAR 재무 | SEC companyfacts JSON | User-Agent 필수, 10 req/s, US-GAAP 태그 정규화 필요 | yfinance 4년 보조 | 7 |
| 종목명→티커 사전 | KRX 상장목록/FDR·SEC company_tickers | 전종목 매칭 오탐 큼 | 시총 상위 50~100 큐레이션 | 5 |
| 계좌 잔고(키움) | Kiwoom TR opw00001/opw00018 | 로컬 32-bit·로그인 세션 필수, CI 불가. 단타·스윙 주력 계좌 — 실현손익 연동 | 직전 스냅샷 + STALE 배지 | 8 |
| 계좌 잔고(한투 위탁·ISA) | KIS REST(앱키·토큰, 읽기전용) | **1개 수집기가 2계좌 담당 — 계좌번호 2건 분리 조회 + 통화 분기**: 위탁=미국주식 전용, USD 원본 잔고 + 적용환율·기준시각(듀얼 표시 필수 필드) / ISA=ETF 전용(KRW), 만기일·납입한도 필드. 데스크톱 수집 한정 | 계좌별 직전 스냅샷 + as_of 유지, DELAYED/STALE 정직 강등 | 8 |
| 계좌 잔고(Bybit) | Bybit v5(읽기전용 키) | 데스크톱 수집 한정. 24h 시장이지만 발행은 1일1회 스냅샷("수집 기준" 캡션 의무, S2) | 직전 스냅샷 + STALE | 8 |

공통 원칙: 실패 = `None` 강등(추정·가짜 데이터 금지, 현행 collectors 원칙 계승), 지수 백오프, runlog 계측 편입(AI Office 가시화). **자산 수집은 4계좌 전량 자동화(키움 TR 로컬 + KIS REST + Bybit v5)** — KB 삭제로 '수기 입력'이라는 데이터 소스 클래스 자체가 소멸했고, Envelope `source:"manual"`은 거시 예상치 YAML(§2-2) 전용으로만 남는다.

---

## 4. 산출 JSON 파일 설계

| 경로 | 채널 | 주요 필드(요지) | 생성 주기 | 소비 페이지 |
|---|---|---|---|---|
| `docs/data/market.json` | docs | 지수·현물·환율·원자재 Envelope 맵 + 스파크라인 배열 | **macro 60분·stock 배치·morning 1회 재수집. news 30분 빌드는 재수집 없이 직전 파일 그대로 재사용**(뉴스만 갱신) | Dashboard·News·Macro |
| `docs/data/macro/indicators.json` | docs | 지표별 {발표치·이전치·추이6·다음발표일·분류} Envelope | 60분 | Macro |
| `docs/data/macro/calendar.json` | docs | 이벤트 {time_kst·event·consensus?·actual?·status·중요도} | 60분 | Macro·News·Dashboard |
| `docs/data/news/index.json` + `YYYY-MM-DD/` | docs | 기사 {id·title·summary·level·impact_tags·first_seen_at·batch_id} | 30분 | News |
| `docs/data/news/counters.json` | docs | 일별 {collected_total·published_total·탭분해} | 30분 | News |
| `docs/data/stock/rankings.json` | docs | KR/US TOP30 + 테마 TOP10 + 합산 스트립 + as_of·session·모집단 | 배치 | Stock |
| `docs/data/stock/hub/{시장}_{티커}.json` | docs | 스탯6·일정·매칭뉴스·테마·TV심볼 | 배치 | Stock Hub·Portfolio |
| `docs/data/financials/{티커}.json` | docs | 5~10년 재무·판정·업종평균? | 일1회 | Financials |
| `docs/data/search-index.json` | docs | 경량 {이름·티커·거래소·현재가} | 일1회 | Financials·Hub |
| `docs/data/ta/preview.json` | docs | KOSPI 지표4 + 60일 시계열 Envelope | 일1회 | TA |
| `docs/data/meta/freshness.json` | docs | 소스별 {expected_T·last_built·source·상태} | 빌드마다 — **build.py 공통 마무리 단계**에서 생성(원료=runlog 확장). 최초 구현 Phase 2 | Settings ④(단일 fetch 소스) |
| `docs/data/assets.enc.json` | docs | **암호문**(AES-GCM). 복호화 시: 4계좌·히스토리·파생 | 데스크톱 | Asset·Portfolio |
| `docs/data/assets.public.json` | docs | 상대값만(%·비중·달성률·수익률) — 절대값·목표금액·투입원금 제외. **게이트 밖 grep 가드 검사 대상 포함** | 데스크톱 — assets.enc.json과 **동일 시점 생성·동일 커밋**. **최초 발행 선행 조건: trades.json 공개 범위 결정(§9-4)** | Asset(게이트 밖 상대값 뷰) |
| `data/snapshots/…` | —(로컬 전용) | 평문 자산 원장 — **단일 진실: `.gitignore` 명시 등재 + 커밋 금지**, pre-commit·CI 경로 차단(§9-4) | 데스크톱 1일 1행 append | (암호문 재료, 발행물 아님) |
| `data/history/rankings/YYYY-MM-DD.json` | data | 전일 순위 스냅샷(소급 불가) | 일1회 | Stock 개선5 |
| `data/history/valuation/{티커}.json` | data | PER/PBR 일별 축적(소급 불가) | 일1회 | Financials 밴드 |

주: 클라이언트 fetch 대상은 반드시 `docs/data/**`(CI `git add docs`). 소급 불가 히스토리 원장만 `data/**`(§7). **재조회 주기는 데이터군별로 분리한다** — '매 빌드 재조회'는 채택하지 않으며, 시세(현재가·시계열) 재수집은 §3의 호출 예산과 §5의 워크플로 배정을 따른다(Yahoo rate limit 방어의 구조 원칙). 종목별 분할은 단일 통합 파일 비대화(수 MB) 회피 목적. 페이지 HTML은 골격만, 값은 JSON을 JS가 채워 diff를 JSON에 국한(커밋 비대화 완화) — 이는 현행 "빌드 타임 렌더"에서 이탈하는 아키텍처 결정이므로 `22-architecture.md`에서 확정.

---

## 5. GitHub Actions 스케줄 설계

### 5-1. 기존 3개 워크플로우(유지)

| 워크플로 | 트리거 | 빌드 | 비고 |
|---|---|---|---|
| morning.yml | cron `30 21 * * 0-4`(KST 월~금 06:30) + push `data/cache/**` | `build.py morning` | Phase 5 정리점에서 **가동 유지·신규 발행만 중단** 판단. `/morning/YYYY-MM-DD/` 영구 보존. 시세 현재가+시계열 1회 재수집 담당 |
| news.yml | cron `*/30` + push | `build.py news` | 30분 유지. **시세 재수집 없음** — market.json은 직전 산출물을 그대로 재사용하고 뉴스·카운터·키워드 레이더만 갱신한다(Yahoo 호출 예산 보호, §3) |
| trades.yml | push `data/trades/**` | `build.py trades` | Portfolio 흡수 후 meta-refresh 안내 |

### 5-2. 신규 워크플로우

| 워크플로 | 트리거 | 갱신 대상 | 통합/분리 근거 |
|---|---|---|---|
| macro.yml | cron 60분 | indicators·calendar + **market.json 시세 재수집(현재가+시계열) 담당** | 관심사 분리(FRED/ECOS 키 env). news 편승 대신 별도 — 시세 호출 예산을 60분 주기로 집중(§3) |
| stock.yml | KR 장중 cron(09:00~15:30 KST 30~60분) + KR 마감 1회 + US 마감 후 1회(KST 새벽) | rankings·hub·search-index + 시세 시계열은 **마감 후 배치에서만** 재조회 | 종목 다건·시차 상이 → 독립 |
| financials.yml | 주중 일1회(DART 야간 배치) | financials·valuation 히스토리 | 저빈도·중량 → 분리 |
| ta는 morning.yml에 편입 | — | ta/preview.json | 단일 지표·저비용, 신규 워크플로 불요 |

자산(Asset/Portfolio)은 **워크플로 cron 없음**. 데스크톱 push(`data/cache/**` 또는 신규 `docs/data/assets*` 경로)가 CI 재빌드를 트리거하는 현행 야간선물 체인과 동일. 계좌 자격증명·평문은 CI에 절대 두지 않는다(4계좌 수집 전부 데스크톱에서 실행, §3).

### 5-3. 공통화 결정

현행 3개 yml의 setup·env·commit 블록은 사실상 복붙(Notion DB ID 4개가 3곳 중복). 페이지·스케줄 증가 전에 **reusable workflow**로 setup(Python 3.12·pip 캐시)·env·commit(`git add docs [data]`)를 단일화. `git add docs`→`git add docs data` 확장은 히스토리 원장 커밋을 위해 Phase 7·8에서 **명시 결정**하되, 확장 대상은 `data/history/**`(전일 순위·PER 밴드)에 **한정**하고 `data/snapshots/`는 대상에서 명시 제외한다(로컬 전용, §9-4). CI에 pytest 단계 추가(현재 0개 워크플로가 테스트 실행).

---

## 6. 신선도(FRESH / DELAYED / STALE / CLOSED-SNAPSHOT) 데이터 요건

빌드 타임에 확정하지 않는다. Envelope의 `as_of_iso`(또는 뉴스 `collected_at`) × `session_key` × 열람 시점 클라이언트 시계로 **JS가 판정**한다(`freshness.js` 단일 모듈, Phase 2 산출). 상태는 design/00 §9-2가 확정한 **4상태(FRESH / DELAYED / STALE / CLOSED-SNAPSHOT)를 정본**으로 하며, 시각 문법(배지·강등 스타일)도 00을 따른다. 다만 **문턱 수치는 본 §6-2 실측표가 단일 진실**이다 — 00의 일반식(경과<T / T~3T / ≥3T)을 GitHub cron 실측 지연(20분~3.7h)에 맞춰 행별로 보정한 값이며, 이 유예 반영은 명시적 설계 결정이다. CLOSED-SNAPSHOT은 오류가 아닌 **1급 상태**다(장 마감 후 정상값).

### 6-1. 판정 규칙(개념)

- **CLOSED-SNAPSHOT(세션 우선)**: `session_key`가 달력상 휴장·마감 구간이면 **나이 판정에 우선해** 이 상태(기준가 병기). 정규장이 아닌 값은 여기 귀속.
- **FRESH**: 세션 open ∧ `age ≤ FRESH 문턱`(행별, 기본 2T — cron jitter 유예). 라이브 점 대신 "약 T 간격 수집" 표기.
- **DELAYED**: 세션 open ∧ `FRESH 문턱 < age ≤ STALE 문턱`. "지연" 배지(`accent.yellow` 아웃라인), 값 색상은 유지(00 §9-2 시각 문법).
- **STALE**: `age > STALE 문턱`(행별). 명도 강등 + STALE 배지, 값은 남기되 정직하게 노출.
- **freshness.js 계약**: 행별 `{fresh_max, delayed_max(옵션), stale_min}` 명시값을 입력으로 받는다. `delayed_max` 부재 행(뉴스 일반)은 FRESH→STALE 직행이며, `fresh_max < stale_min`인 행은 그 사이 구간을 **반드시 DELAYED로 배정**한다 — 어떤 행에도 미정의 구간이 존재해서는 안 된다.

### 6-2. 소스별 expected_T·문턱 실측표

GitHub cron 실측 지연(20분~3.7h) 반영, FRESH는 2T 유예. 절대·상대 문턱 병기. **전 행에 DELAYED 열을 명시해 미정의 구간을 소거**한다.

| 데이터군 | expected_T | FRESH(세션 open) | DELAYED | CLOSED-SNAPSHOT | STALE | basis |
|---|---|---|---|---|---|---|
| 시세(장중 현물·지수) | 30분 | age ≤ 60분 | 60분 < age ≤ 90분 | 세션 closed ∧ age ≤ 26h | age > 90분(장중) / > 26h(마감) | as_of |
| 환율(ECB) | 24h | age ≤ 26h | 26h < age ≤ 50h | 주말·공휴일 | age > 50h | as_of |
| macro 지표·금리 | 60분 | age ≤ 120분 | 120분 < age ≤ 180분 | — | age > 180분 | as_of |
| 뉴스 일반 | 60분 | age ≤ 90분 | —(직행, delayed_max 부재) | — | age > 90분 | collected_at |
| 뉴스 속보 | 30분 | age ≤ 45분 | 45분 < age < 90분 | — | age ≥ 90분 | collected_at |
| TA/재무(일봉·EOD) | 24h | age < 24h | 24h ≤ age < 72h | 항상 EOD 스냅샷 | age ≥ 72h | as_of |
| 야간선물 | (자동 미지원) | — | —(2상태 운용) | 세션 closed ∧ age ≤ 60h | age > 60h | as_of |
| 자산(자동 수집, 4계좌 공통) | 24h | age ≤ 26h | 26h < age ≤ 50h | — | age > 50h | as_of |

- 야간선물 상태 A(● LIVE·T=10분)는 **지원 범위 제외**(Kiwoom 데스크톱 수동 의존). CLOSED-SNAPSHOT·STALE 2상태로 운용, 현행 60h·flat 차단 로직을 공통 규칙 위에서 재사용.
- TA/재무 행의 DELAYED 24~72h 구간은 로드맵 Phase 2 DoD의 강등 재현 시나리오(FRESH→DELAYED→STALE)와 일치하는 검증 기준값이다.
- 자산 행은 **단일 규칙**이다 — KB 수기 특례(T=7일/STALE>14일)는 KB 삭제와 함께 소멸했고, 4계좌 전부 데스크톱 자동 수집이므로 T=24h 하나로 수렴한다. 데스크톱 미실행 일자는 이 규칙에 따라 DELAYED→STALE로 정직하게 강등된다.

### 6-3. 세션·휴장 달력 규격 (`config/calendar.py`)

| 필드 | 의미 |
|---|---|
| `market`(kr/us) | 대상 시장 |
| `regular`{open,close} | 정규장 시각(KST/ET) |
| `holidays[]` | 연 1회 수기 관리 휴장일(YYYY-MM-DD) |
| `pre/post` | 장전·장후 구간(카운트다운·CLOSED-SNAPSHOT 판정) |

저빈도(연 1회) 정적 데이터. 자동 소스 불요. 카운트다운·세션 라벨·마감/장중 배지가 이 달력 + 클라이언트 시계를 공유한다.

### 6-4. 결측 강등 문법(옵션 필드 목록)

무료 소스 부재 시 **빈칸 렌더가 아니라 축소·생략**한다.

| 옵션 필드 | 부재 시 처리 |
|---|---|
| 경제지표 예상치/서프라이즈 | 열 생략(수기 YAML 입력 시에만) |
| 업종평균 기준선 | 자사 5y 단독 판정 |
| 야간선물 라이브·스파크라인 | 상태 A 제외, 스파크 생략 |
| Hero 해석 문장 | 문장 행 생략(팩트 우선) |
| Hub 일정 IR·규제·락업 | 계약 3종으로 축소 |
| PER 등 불안정 스탯 | 셀 생략 |
| Fear&Greed 카드 | 4열→3열 폴백 |

---

## 7. 히스토리 원장: `data/` vs `docs/data/` 분리 기준

| 기준 | `docs/data/**` | `data/**`(히스토리 원장) |
|---|---|---|
| 성격 | **재조회 가능** — 소스 API가 히스토리 제공 | **소급 불가** — 오늘 놓치면 영구 결손 |
| 예시 | 시세·스파크라인(yfinance history)·환율 30일(Frankfurter)·지표(FRED)·재무(DART/EDGAR) | 전일 순위 스냅샷·PER/PBR 일별 밴드 |
| 커밋 주체 | CI `git add docs` — 재조회는 **담당 워크플로 주기**(§5 배정)로 수행, 매 빌드 아님 | 데스크톱/CI, `git add docs data` 확장 결정 필요(대상은 `data/history/**` 한정, §5-3) |
| 원칙 | 누적 저장소 신설 금지, 담당 워크플로에서 재조회(호출 예산 §3) | 최소 필드만 append, 커밋 비대화 관리 |

원칙: 소스가 히스토리를 API로 주면 재조회(누적 금지)가 정답. 진짜 소급 불가 데이터만 `data/`에 커밋한다. **자산 평문 원장(`data/snapshots/`)은 `data/` 커밋 대상이 아니라 로컬 전용이다** — §9-4가 단일 진실이며, 22-architecture·20-roadmap에 남은 '스냅샷 커밋' 서술은 이 조항 기준으로 정렬되어야 한다.

---

## 8. 유니버스 정의 + 모집단 캡션 규칙

| 유니버스 | 정의 | 소비 |
|---|---|---|
| 시세 유니버스 | `config/markets.py` 확장(현행 Yahoo 5심볼 = 4지수+WTI → 20+): 현물·VIX·DXY·원자재·선물·금리·BTC. 현행 market.json 8지표 = 이 5심볼 + 환율(frankfurter 우선 3단 폴백) + 야간선물 2종(kiwoom 캐시) | Dashboard·Macro·News |
| 종목 유니버스 | `config/universe.py` = TOP30×2 ∪ 테마 종목(`config/themes.py`) ∪ Notion watchlist. 일 100~200종목 | Stock·Hub·Financials·Portfolio |
| 테마 매핑 | `config/themes.py`: 테마→[종목(티커·시장·대표여부)]. 복수 소속은 대표1+전체 | Stock·Hub |

**모집단 캡션 규칙**: 미국 "전시장 TOP30"은 무료 불가 → "유니버스 N종목 중 TOP30"으로 캡션 명시(정직한 축소). 유니버스 밖 종목 클릭 = Hub 빈 상태(design 05 §2-5). 온디맨드 조회 불가는 정적 사이트의 구조적 한계로 문서에 명시.

---

## 9. Asset / Portfolio 프라이버시 처리 (확정: A + D)

현행 `templates/dashboard.html`(36~88행 `{% if erp %}` 블록)은 Notion assets가 차는 순간 총자산·유형별 금액·목표·현금흐름을 **공개 대시보드에 평문 렌더**하는 구조다. `data/trades/trades.json`은 이미 단가·수량·실현손익이 평문 공개 커밋 상태다. 클라이언트 비번 게이트는 접근 제어가 아니며(JSON 직접 열람·git 히스토리로 우회), 공개 리포 + 평문 전제에서는 "가림"조차 성립하지 않는다. 따라서 **데이터 처리 방식**을 코드 이전에 확정한다.

### 9-1. 채택안 A + D

- **A(암호화 발행)**: 데스크톱이 passphrase 파생키로 암호화한 `docs/data/assets.enc.json`(암호문)만 커밋. 게이트 비밀번호 = 복호화 passphrase, **복호화 성공 = 인증**(비번 해시 저장 안 함). 90일 히스토리·파생값은 암호문 payload 내부에 포함.
- **D(마스킹 공개)**: 게이트 밖 공개 뷰 `assets.public.json` — **데스크톱이 암호문과 동일 시점에 생성해 같은 커밋으로 발행**한다. 상대값만 — 등락%·수익률%·비중%·달성률%. **절대값·목표금액·투입원금·예수금은 전부 제외**(역산 방지). 게이트 밖 grep 가드(§9-3)의 검사 대상에 명시 포함되며, Asset 게이트 밖 화면이 이 파일 하나만 fetch한다.

### 9-2. KDF·암호 파라미터(데이터 정책)

암호문이 공개되므로 오프라인 무차별 대입이 가능 → 강한 KDF + 긴 passphrase 필수. 브라우저 복호화는 WebCrypto 사용.

| 항목 | 값 | 근거 |
|---|---|---|
| KDF | PBKDF2-HMAC-SHA256, iterations ≥ 600,000 (WebCrypto 네이티브). Argon2id 채택 시 WASM 인라인 필요 | 브라우저·데스크톱 동일 알고리즘 |
| salt | 파일당 16바이트 랜덤 | 레인보우 방지 |
| 암호 | AES-256-GCM, IV 12바이트 | 인증 암호화 |
| passphrase | **최소 길이·엔트로피 강제**(Settings "4자" 정책 폐기·개정) | 오프라인 공격 내성 |

### 9-3. 마스킹(역산 방지) 범위

절대 금액을 다 가려도 목표금액(₩250M) + 달성률(74.5%)이 함께 공개되면 총자산이 역산된다. 공개 정책은 **목표금액·투입원금 포함 전 절대값**을 일괄 비공개한다. 같은 원리의 또 다른 역산 경로가 이미 열려 있다: 평문 공개 상태인 `trades.json`의 보유 수량×단가에서 키움 계좌 평가액 절대치가 근사 산출되고, 여기에 `assets.public.json`의 계좌 비중%를 결합하면 총자산이 역산된다 — 그래서 §9-4 3항이 두 산출물의 **발행 순서**를 규정한다. 게이트 밖 grep으로 절대값·역산 가능 값 0건(**검사 대상: assets.public.json·trades.json 포함 게이트 밖 전체**)이 완료기준.

### 9-4. 선결 조치 & 가드

1. **Phase 4 선차단**: `dashboard.html` 자산 섹션 제거 또는 상대값화(Notion 데이터가 차기 전에).
2. **평문 오커밋 방지 가드(단일 진실)**: 평문 스냅샷 원장 `data/snapshots/`는 **로컬 전용 — `.gitignore` 명시 등재 + 커밋 금지**가 3문서 공통의 단일 진실이며, 90일 히스토리는 암호문 payload 내부로만 발행한다. 현행 `.gitignore`는 `data/cache/` 커밋을 허용하는 구조라(주석으로 확인) `data/snapshots/`를 **명시적으로 제외하지 않으면 실제로 커밋된다** — Phase 8 착수 시 `.gitignore`에 `data/snapshots/` 추가를 체크리스트로 선행한다. pre-commit·CI 가드는 `docs/**`·`data/**`의 절대금액 패턴 차단에 더해 **`data/snapshots/` 경로 유입 자체를 차단 패턴에 포함**한다. git 히스토리는 삭제 불가 — 한 번의 오커밋이 영구 사고이므로 가드가 발행보다 선행한다. (22-architecture §7-1의 '원장, 커밋'·20-roadmap의 data/ 커밋 후보 서술은 본 조항으로 정렬 대상이다.)
3. **매매 원장 공개 범위 결정 = `assets.public.json` 최초 발행의 선행 조건**: `trades.json` 수량·단가의 마스킹 또는 암호문 이전 여부를 **assets.public.json을 처음 발행하기 전에** 결정·적용한다(발행 순서 규정 — §9-3의 역산 경로 차단). Phase 8 DoD '역산 가능값 grep 0건'의 검증 대상에 trades.json을 명시적으로 포함한다.
4. **모순 해소**: 비밀번호 변경 = 데스크톱 재암호화·재커밋(클라이언트만으로 완결 불가) → Settings ③ 변경 모달을 "데스크톱에서 재발행" 안내로 정정. passphrase 분실 = 복구 불가 고지.

상위 호환 대안 B(로컬 전용 미커밋)는 원격·모바일 열람을 포기할 수 있을 때의 선택지로 남긴다.

---

## 10. 미결 사항(결정 필요)

| # | 사안 | 결정 시점 |
|---|---|---|
| 1 | 값=JSON/JS 채움 vs 빌드 타임 렌더(커밋 diff 국한) | `22-architecture.md`(Phase 1) |
| 2 | `git add docs` → `git add docs data` 확장 시점(대상은 `data/history/**` 한정 확정, `data/snapshots/` 제외 확정 — §5-3·§9-4) | Phase 7·8 착수 시 |
| 3 | Argon2id(WASM 인라인) vs PBKDF2 600k 최종 채택 | Phase 8 착수, Phase 4에서 정책 결정 |
| 4 | `trades.json` 단가·수량 공개 유지 여부 — **`assets.public.json` 최초 발행의 선행 조건**(§9-4 3항) | Phase 8 착수 시, public 발행 이전 |
| 5 | 모닝 생성기 발행 중단 시점(가동은 유지) | Phase 5 정리점 |
| 6 | ISM 제조/서비스 대체 소스 확보 여부 | Phase 6(미확보 시 행 제외) |
