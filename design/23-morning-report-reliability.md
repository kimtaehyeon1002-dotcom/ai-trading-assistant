# 23 — 모닝리포트 신뢰도 개선 설계 (시세 파이프라인 전면 점검)

작성: 2026-07-24 · 상태: **설계(구현 전, 승인 대기)**

사용자 보고 증상 2건에서 출발한 전 모듈 점검 결과와 개선 설계.

- 증상 1: 리포트 갱신이 `run_desktop*.bat` 수동 실행에 묶여 있음 → 하루 2회 자동 수집 필요.
- 증상 2: 코스피 야간선물 실제 +1.70%인데 리포트는 -0.06%. 코스닥 야간선물은 아예 안 보임.
  미국 지수도 신뢰 불가.

---

## 1. 점검 범위와 데이터 흐름(현행)

```
[야간선물]  app/sync.py(데스크톱, 수동) → kiwoom_desktop/futures.py(opt50001)
            → data/cache/kiwoom_night.json(커밋) → push → CI 재빌드
[미국/글로벌] news.yml(30분 cron) → market_collector.py(yfinance fast_info)
            → data/cache/market_last.json(커밋)
[조립]      validators/market_validator.py → repositories/market_repository.py
            → docs/data/market.json → dashboard_v2 타일(+freshness.js 배지)
[모닝 빌드] morning.yml: KST 06:30 cron + data/cache/** push 트리거
```

점검 모듈: `market_collector` `kiwoom_collector` `kiwoom_desktop/futures`
`market_validator` `market_repository` `config/markets` `config/settings`
`generators/morning` `generators/dashboard_v2` `app/sync` + 워크플로 3종 + 실데이터/로그.

---

## 2. 확인된 문제(재현 근거 포함)

### P1. 자동 수집 부재 — 스케줄러 미등록 (증상 1의 원인)
`run_desktop_auto.bat`은 작업 스케줄러용으로 만들어졌지만 **등록 절차가 어디에도 없고,
실제 `schtasks` 조회 결과 등록된 작업이 0건**. 야간선물은 사용자가 bat을 손으로 돌릴
때만 갱신된다.

### P2. 야간선물 -0.06% — "세션 밖 실행 → 폐기 → 31시간 묵은 값 표시" (증상 2-1의 원인)
`sync_auto.log`(07-24 06:04 실행)로 전 과정 확정:

1. KRX 야간장은 **익일 05:00 마감**. 06:04 실행 시 opt50001은 `현재가=기준가=1132.50`,
   등락 0.00% — 야간 세션 정보가 이미 사라진 스냅샷.
2. `app/sync.py`의 flat 필터(등락 0.0 → 저장 제외)가 이를 폐기 — *그 자체는 올바른 동작*.
3. 결과적으로 `kiwoom_night.json`에는 **07-22 23:12 KST** 값(-0.06%)이 남고,
4. `NIGHT_FUTURES_MAX_AGE_H=60h`(주말 갭 커버용) 안이라 validator 통과 →
   07-24 아침 대시보드에 이틀 전 값이 최신처럼 표시.

즉 계산식이 틀린 게 아니라 **수집 시각이 세션과 어긋났고, 만료 정책이 평일에도 60h**라서
낡은 값이 살아남은 것. 07-23 밤 세션(+1.70%)은 아무도 수집하지 않았다.

### P3. 코스닥 야간선물 미표시 — 대시보드 타일에 키 자체가 없음 (증상 2-2의 원인)
데이터는 존재한다(`kiwoom_night.json`에 kosdaq_night 있음, futures.py도 정상 조회).
그러나 `generators/dashboard_v2/generate.py:24`
`_KR_TILE_KEYS = ("kospi", "kosdaq", "kospi_night", "usdkrw")` 와
`templates/pages/dashboard_v2.html:40` 루프에 **kosdaq_night가 빠져 있다**.
(모닝 dated 페이지는 은퇴됐으므로 대시보드가 유일한 표시면 — 여기 없으면 어디에도 없음.)

### P4. 미국/글로벌 시세 — 단일 소스, 교차검증·상한 없음

> **구현 중 정정(2026-07-24 실측).** 설계 시점에는 "등락률이 틀어졌을 것"으로 추정했으나,
> 독립 소스(FinanceDataReader)와 대조한 결과 **현재 값들은 모두 정확했다**:
> nasdaq -2.15 / sp500 -1.21 / dow -0.97 / vix 11.98 / **kospi +4.40 / kosdaq +5.22**
> — 6개 전부 두 소스가 일치(kospi·kosdaq의 극단값도 실제 시장 움직임이었다).
> 즉 P4는 "값이 틀렸다"가 아니라 **"맞는지 틀린지 판단할 근거가 없다"**가 정확한 문제였다.
> 사용자가 미국 증시까지 못 믿게 된 것은 같은 화면에서 야간선물이 이틀 낡은 값을 보여준
> 탓이 크다(P2가 화면 전체의 신뢰를 깎았다). 아래 개선은 그대로 유효하되, 목적은
> "틀린 값 교정"이 아니라 **"근거 부여 + 앞으로 틀어질 때 감지"**로 재정의한다.
`market_collector._yahoo()`는 yfinance `fast_info`의 `last_price/previous_close` 한 쌍으로
등락률을 만든다. 알려진 약점:

- 세션 경계·휴장일에 `previous_close`가 며칠 전 종가로 잡히거나 당일 종가와 뒤섞여
  **등락률이 통째로 틀어지는** 사례가 잦음(교차검증 없이는 탐지 불가).
- 실제 커밋 캐시(07-23)에 kospi +4.40%, kosdaq +5.22% 같은 극단값이 **무검증 통과**로
  기록돼 있음 — 참이든 거짓이든 현재 구조는 구분할 수단이 없다.
- 지수별 세션 시간을 모르는 채 30분 cron이 아무 때나 찍으므로, 표시 시점 기준
  "어제 종가 대비 몇 %인지"의 의미가 시각마다 달라진다.

### P5. (부차) 신선도가 배지에만 있고 값 옆에 없음
Envelope에 `as_of_iso`는 있으나 타일 숫자 옆에 기준 시각이 상시 노출되지 않아,
P2 같은 stale 값을 사용자가 최신으로 오독한다.

---

## 3. 개선 설계

### A. 자동화(P1) — 작업 스케줄러 2회/일 등록
등록 스크립트 `scripts/register_schedule.ps1`(1회 실행, 관리자 불필요·현재 사용자 컨텍스트) 신설:

| 작업명 | 시각(KST) | 요일 | 목적 |
|---|---|---|---|
| ThBot-NightFutures-AM | **04:40** | 화~토 | 야간장 마감(05:00) 직전 스냅샷 = 모닝리포트의 "밤사이 변동" 확정치 |
| ThBot-Sync-PM | **22:30** | 월~금 | 야간장 초반 시세 + 당일 체결 동기화 |

- 실행 대상: 기존 `run_desktop_auto.bat`(로그·타임아웃 로직 재사용).
- `-WakeToRun`(절전 해제) + `-StartWhenAvailable`(놓친 실행 보충) 설정.
- 전제조건 문서화: Kiwoom OpenAPI AUTO 로그인 저장, PC 전원/절전 정책.
- 04:40 수집 → push → `morning.yml` push 트리거로 06:30 이전에 리포트 반영(현행 트리거 재사용, CI 변경 없음).

### B. 야간선물 정확도(P2)
1. **세션 인지 수집**: 야간장 창(18:00~익일 05:00 KST)을 `config/calendar.py`에 정의하고
   수집 전에 판정. 창 밖이면 조회 자체를 하지 않고 사유를 남긴다(종전에는 '유효 시세 없음'
   경고 하나로 "세션 밖이라 없음"과 "세션 중인데 비정상"이 구분되지 않았다).
2. **만료 이원화**: 표시 만료를 `평일 20h / 주말 경유만 60h`로 분리
   (금요일 밤 값의 월요일 아침 표시는 유지, 평일 한 세션 낡은 값은 차단).
   - **20h 근거(설계 시 26h → 구현 시 하향)**: 26h는 *어제 새벽* 값(25.8h)을 통과시켜
     "한 세션 낡은 값 차단"이라는 목적을 달성하지 못한다. 정상 경로의 최장 나이는
     세션 개시(18:00) 직후 수집분이 다음 날 06:30 리포트에 실리는 12.5h이므로,
     20h면 정상 경로를 모두 덮으면서 25.8h를 확실히 탈락시킨다.
   - 주말 판정은 "구간(as_of→now)에 토·일이 포함되는가"로 한다.
3. **flat 필터 유지**: 0.0% 폐기는 올바른 방어이므로 그대로 두되, 폐기 사유를
   `kiwoom_night.json`에 `last_skip`으로 남겨 진단 가능하게(갱신 성공 시 자동 제거).
4. A의 04:40 스케줄이 본질 해결 — 마감 20분 전 실측치가 매일 아침 존재하게 된다.

### C. 코스닥 야간 타일(P3)
- `_KR_TILE_KEYS`에 `kosdaq_night` 추가, `dashboard_v2.html` 루프 키에 추가.
- `test_dashboard_v2.py`에 kosdaq_night 타일 렌더 검증 추가.

### D. 미국/글로벌 시세 신뢰도(P4) — 실측으로 2건 수정됨

1. ~~등락률 산출을 `history()` close-to-close로 교체~~ → **철회.**
   실측 결과 yfinance 일봉 히스토리는 **국내 지수에서 하루 늦다**(^KS11 최신일 07-22,
   실제 07-23 마감 존재). 이대로 바꿨으면 코스피/코스닥이 하루 낡은 값으로 퇴행했다.
   `fast_info`는 두 지수 모두 당일 값을 정확히 준다 → **현행 유지**가 옳다.
   - 다만 `fast_info` 키가 버전마다 snake/camel로 갈리고 1.5.1은 camelCase만 값을 준다.
     기존 `or` 폴백이 이를 우연히 막고 있었으므로, 필수 장치임을 코드에 명시한다.
2. ~~Stooq 교차검증~~ → **FinanceDataReader로 교체.**
   Stooq는 인덱스 심볼(`^spx`·`^kospi` 등) 전부 404 — 사용 불가로 확인.
   FinanceDataReader는 **이미 requirements에 있는 기존 의존성**이고(랭킹 수집기가 사용)
   백엔드가 Yahoo와 달라 독립 대조군이 된다 → 신규 의존성 0으로 2소스 확보.
   - 대조 대상: sp500·nasdaq·dow·vix·kospi·kosdaq (6종)
   - 등락률 차 ≤ 0.5%p → `quality: "verified"`, 초과 → `"degraded"`(값은 유지 —
     어느 쪽이 옳은지 알 수 없으므로 임의 판정하지 않는다), 대조 불가 → `"unverified"`
   - Yahoo 결측 시 대조 소스 값으로 대체(추정이 아니라 다른 소스의 사실)
3. **sanity bound**: 소스 오류(자릿수 밀림·기준가 오배정)만 걸러내도록 **넉넉히** 잡는다.
   설계 초안의 "지수 12%"는 실제 폭락일(1987 다우 -22.6%)을 잘라내므로 25%로 상향.
   VIX·MOVE 150%(단일일 +115% 전례), 환율 10%, 원자재 40%, BTC 50%.
   폭락일에 값이 사라지는 것이 나은 선택이라는 보장은 없다 — 그날이야말로 봐야 하는 날이다.
4. 책임 분담 유지: collector=수집·교차, validator=범위·신선도.
   `quality`는 Envelope 정식 필드로 승격(schema/envelope.schema.json에 enum 등재).

### E. 신선도 상시 노출(P5)
- 대시보드 타일에 `as_of`(MM-DD HH:MM)를 항상 소자로 표기(배지 hover가 아니라 상시).
- `docs/data/meta/freshness.json`에 소스별 last-success 타임스탬프 추가(이미 생성 중인
  파일 확장) → "마지막으로 언제 성공했나"를 한 눈에.

---

## 4. 구현 순서(승인 후)

| 단계 | 상태 | 내용 | 파일 | 검증 |
|---|---|---|---|---|
| 1 | **완료** | C: 코스닥 야간 타일 | dashboard_v2/generate.py, dashboard_v2.html, components.css, 테스트 | pytest 15 + 렌더 육안 확인 |
| 2 | **완료** | B: 세션 인지 + 만료 이원화 | calendar.py, settings.py, market_validator.py, futures.py, sync.py, kiwoom_collector.py, 테스트 | pytest 197 + 실캐시 재현(아래) |
| 3 | **완료** | D: FinanceDataReader 교차검증 + sanity bound + quality 필드 | market_collector.py, market_validator.py, markets.py, envelope.schema.json, market.py, market_repository.py, 테스트 | pytest 210 + 라이브 수집 실측(아래) |
| 4 | **스크립트 완료 · 등록 대기** | A: 스케줄러 등록 스크립트 | scripts/register_schedule.ps1 | 구문 검증 + 두 시각 모두 세션 창 내부 확인. **등록은 사용자 승인 후 실행** |
| 5 | **완료** | E: as_of 상시 표기 + degraded 경고 | market_repository.py, dashboard_v2.html, components.css, 테스트 | pytest 215 |

**2단계 실캐시 재현 결과(2026-07-24 07:08 KST)** — 개선 전 대시보드에 표시되던 값이
새 규칙에서 실제로 탈락하는 것을 확인:

```
cache     kospi_night  = (-0.06%, 2026-07-22T14:12Z)   ← 31h, 주말 없음
validated kospi_night  = None                          ← 탈락(종전 60h 규칙에선 통과)
validated kosdaq_night = None
now KST: 2026-07-24 07:08 Fri  night_session: False     ← 06:04 동기화가 세션 밖이었음이 확정
```

4단계(스케줄러) 적용 전까지 야간선물 타일은 "데이터 없음"으로 비는 것이 정상이다 —
틀린 값을 지우는 것이 먼저이고, 채우는 것은 4단계다.

**3단계 라이브 수집 실측(2026-07-24 07:2x KST)** — 20심볼 수집, 폐기 0건:

```
verified(2소스 일치): nasdaq -2.15 · sp500 -1.21 · dow -0.97 · vix +11.98
                      kospi +4.40 · kosdaq +5.22
degraded            : (없음)
dropped             : (없음)
```

코스피 +4.40%·코스닥 +5.22%가 두 독립 소스에서 동일하게 나온다 — **봇이 틀린 값을 실은 것이
아니었다.** 다만 이제는 그 사실을 `quality: verified`로 데이터에 남긴다.

실환경 검증 필요 항목(코드만으로 확정 불가): 04:40 opt50001 응답 형태(야간 세션 중
기준가 필드), Stooq 심볼 매핑(^KS11↔`^kospi` 등), 절전 해제 동작.

---

## 5. 이번에 고치지 않는 것(범위 밖)

- 뉴스 모듈 전반 — 다음 점검 사이클(사용자 예고).
- 모닝 dated 페이지 재발행 — 은퇴 결정(design/20 Phase 9) 유지, 표시면은 대시보드.
- 야간선물 등락 기준(전일 정규장 종가 대비) 자체는 거래소 관례와 일치 — 변경 없음.
