# AI Trading Assistant

개인용 트레이딩 어시스턴트 — **정적 사이트(GitHub Pages)** 로 발행하는 다크 테마 v2 셸(단일).
서버·DB·유료 API 없이 **GitHub Actions + GitHub Pages** 로 무료 운영한다.

## 페이지
- **Dashboard** `/` · **Macroeconomics** `/macro/` · **News** `/news/` · **Stock** `/stock/`
  (+ Stock Hub 전역 패널) · **Financial Statements** `/financials/` · **Technical Analysis** `/ta/`
- **Asset** `/asset/` 🔒 · **Portfolio** `/portfolio/` 🔒 — 비밀번호 게이트(WebCrypto 복호화, `utils/crypto.py`)
- **매매일지** `/trades/`(공개) · **Settings** `/settings/` · **AI Office** `/ai-office/`(orphan, nav 미노출)
- **모닝리포트**(`/morning/YYYY-MM-DD/`)는 신규 발행이 영구 중단된 동결 아카이브 — 기존 링크만 보존

## 빌드
```bash
pip install -r requirements.txt
python build.py all        # 타깃 목록은 generators/registry.py 참조, 예: stock | financials | asset | all
python -m http.server --directory docs   # 로컬 미리보기
```

## 구조 (계층: collectors → validators → repositories → calculators → generators, 역방향 금지)
```
build.py            조립 루트 — CLI·데스크톱 공용 빌드 디스패치(run_build)
config/             경로·사이트·RSS 피드·키워드·시장 유니버스·nav 단일 소스(nav.py) (로직 없음)
utils/              로깅·날짜(KST)·JSON IO·runlog·crypto(PBKDF2+AES-GCM) (작은 헬퍼만)
models/             dataclass: Quote/NewsArticle/Trade/MorningReportData
collectors/         다운로드/스캔 전용(market/news/obsidian vault/kiwoom_desktop/krx·us_ranking/dart/edgar/kis/bybit 등)
validators/         결측/중복/형식/신선도 검증 (불합격 → None/생략)
repositories/       raw → 모델 변환 + 저장(cache JSON·매매 원장·자산 암호화 발행)
calculators/        순수 계산(카테고리/테마/랭킹/매매 통계/재무 지표/자산 지표)
generators/         Jinja2 렌더 → docs/(registry.py가 타깃별 디스패치; v1 셸은 Phase 9에서 은퇴)
templates/ static/  v2 셸 단일(base_v2.html), 토큰 CSS(tokens.css), 페이지별 JS
data/trades/        커밋되는 매매 원장(trades.json) · data/snapshots/는 자산 로컬 원장(커밋 금지)
app/                PyQt5 데스크톱(main.py: 빌드·Kiwoom 동기화·배포 push)
.github/workflows/  각 데이터 도메인별 자동화(morning·news·stock·financials·macro 등)
```

## GitHub Pages 설정
1. 저장소 push 후 **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**.
2. workflow의 `contents: write` 권한으로 생성 결과가 자동 커밋/배포된다.

## 자산 평문 유출 가드 (Asset/Portfolio 작업 전 1회 설치)
Asset/Portfolio는 개인 자산(계좌 잔고)을 다루므로, 절대금액이 실수로 공개 저장소에 커밋되는
사고를 막는 로컬 pre-commit 훅을 제공한다. 클론 직후 1회 설치:
```bash
git config core.hooksPath .githooks
```
CI에도 동일 검사(`.github/actions/guard-plaintext`)가 최종 방어선으로 걸려 있다(로컬 훅은
클론마다 수동 설치라 누락될 수 있고, github-actions bot 커밋은 훅을 거치지 않기 때문).

## Kiwoom (매매일지 자동 기록)
키움 OpenAPI+ OCX는 **Windows 32-bit Python + KOA Studio** 설치 환경 필요.
`run_desktop.bat`(또는 `python -m app.main`) → 로그인 → 동기화 → `data/trades/trades.json` 갱신
→ 「커밋+푸시(배포)」 버튼 → push가 trades workflow를 트리거해 대시보드 재생성.

## Asset/Portfolio 자산 수집 (데스크톱 전용)
4계좌(키움 · 한투 위탁 · 한투 ISA · BYBIT) 잔고 수집은 **데스크톱에서만** 실행한다 —
계좌 자격증명과 평문 자산 원장을 CI에 두지 않기 위한 결정이다(design/21 §281). GitHub Actions에는
자산 워크플로가 없고, 데스크톱이 만든 암호문(`docs/data/asset/assets.enc.json`)만 push된다.

1. `.env.example`을 `.env`로 복사하고 값을 채운다(`.env`는 gitignore 대상 — 절대 커밋되지 않는다).
   - `ASSET_PASSPHRASE` = 게이트 비밀번호 겸 암호화 키. 바꾸면 데스크톱에서 재발행해야 한다.
   - **KIS 앱키는 계좌마다 따로 발급해야 한다** — 앱키는 발급 시 연결한 계좌에만 유효하다(실측
     확인: 위탁 앱키로 ISA를 조회하면 상품코드를 무엇으로 바꿔도 `INVALID_CHECK_ACNO`).
     위탁 = `KIS_APP_KEY/SECRET` + `KIS_ACCOUNT_FOREIGN`,
     ISA = `KIS_ISA_APP_KEY/SECRET` + `KIS_ACCOUNT_ISA`(ISA 키를 비우면 공용 키로 폴백).
     계좌번호는 하이픈 포함/미포함 아무 형식이나 된다.
   - `BYBIT_API_KEY/SECRET` — 키 타입은 **HMAC**(RSA 아님), 권한은 **Read-Only**로 발급할 것.
2. `python -m app.sync`(매매 동기화에 이어 자산까지) 또는 `python -m app.main` → 「자산 동기화(4계좌)」.
3. 「커밋+푸시(배포)」로 암호문을 발행한다.

수집 실패 시 원칙: 확보되지 않은 계좌는 **결측**으로 남고 가짜 값을 만들지 않는다. 4계좌 전부
실패하면 발행 자체를 건너뛰어 직전 발행물을 유지하고, 신선도 규칙(24h 기준 DELAYED→STALE)이
화면에서 낡음을 드러낸다. 일부만 실패한 날은 발행하되 **스냅샷 원장 기록은 보류**한다 —
결측분만큼 낮은 합계가 원장에 남으면 다음 날 전일 대비가 수집 실패를 자산 급락으로 보여준다.

> 정보·참고용 도구이며 투자 판단의 책임은 본인에게 있습니다.
