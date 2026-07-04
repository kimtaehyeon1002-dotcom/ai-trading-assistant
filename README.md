# AI Trading Assistant

개인용 트레이딩 어시스턴트 — **정적 사이트(GitHub Pages)** 로 발행하는 모닝리포트 / 뉴스 센터 / 매매일지.
서버·DB·유료 API 없이 **GitHub Actions + GitHub Pages** 로 무료 운영한다.

## 모듈
- **모닝리포트** — 지수/선물/환율/핵심뉴스/경제캘린더/워치리스트 → `docs/morning/YYYY-MM-DD/index.html` (평일 06:30 KST)
- **뉴스 센터** — 한국/미국·AI·반도체·매크로·속보 (RSS + 키워드 분류) → `docs/news/index.html` (30분마다)
- **매매일지** — Kiwoom 체결 자동 기록, 단타/스윙/장기 분류, 승률/손익 대시보드 → `docs/trades/index.html`

## 빌드
```bash
pip install -r requirements.txt
python build.py all        # morning | news | trades | dashboard | all
python -m http.server --directory docs   # 로컬 미리보기
```

## 구조 (계층: collectors → validators → repositories → calculators → generators, 역방향 금지)
```
build.py            조립 루트 — CLI·데스크톱 공용 빌드 디스패치(run_build)
config/             경로·사이트·RSS 피드·키워드·시장 유니버스 (로직 없음)
utils/              로깅·날짜(KST)·JSON IO·runlog (작은 헬퍼만)
models/             dataclass: Quote/NewsArticle/Trade/MorningReportData
collectors/         다운로드 전용 (market/news/notion/kiwoom 캐시, kiwoom_desktop/)
validators/         결측/중복/형식/신선도 검증 (불합격 → None/생략)
repositories/       raw → 모델 변환 + 저장 (cache JSON·매매 원장)
calculators/        순수 계산 (카테고리/테마/랭킹/매매 통계)
generators/         Jinja2 렌더 → docs/ (morning/news/trades/dashboard/ai_office)
templates/ static/  다크 테마 HTML/CSS/JS (No React)
data/trades/        커밋되는 매매 원장(trades.json) · cache/는 미커밋 재생성물
app/                PyQt5 데스크톱(main.py: 빌드·Kiwoom 동기화·배포 push)
.github/workflows/  morning · news · trades 자동화
```

## GitHub Pages 설정
1. 저장소 push 후 **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**.
2. workflow의 `contents: write` 권한으로 생성 결과가 자동 커밋/배포된다.

## Kiwoom (매매일지 자동 기록)
키움 OpenAPI+ OCX는 **Windows 32-bit Python + KOA Studio** 설치 환경 필요.
`run_desktop.bat`(또는 `python -m app.main`) → 로그인 → 동기화 → `data/trades/trades.json` 갱신
→ 「커밋+푸시(배포)」 버튼 → push가 trades workflow를 트리거해 대시보드 재생성.

> 정보·참고용 도구이며 투자 판단의 책임은 본인에게 있습니다.
