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

## 구조
```
build.py            CLI 엔트리(생성기 디스패치)
config/             경로·사이트·RSS 피드·시장 유니버스
core/               로깅·날짜(KST)·JSON IO
models/             dataclass: Quote/NewsArticle/Trade/MorningReportData
services/           데이터 수집 + 도메인(수집과 생성 분리)
  market/  news/  kiwoom/  report/  github/  journal.py
generators/         Jinja2 렌더 → docs/ (morning/news/trades/dashboard)
templates/ static/  다크 테마 HTML/CSS/JS (No React)
data/               trades/·reports/·cache/  (economic_calendar.json)
app/main.py         PySide6 데스크톱(빌드 트리거 + Kiwoom 동기화)
.github/workflows/  morning · news · trades 자동화
```

## GitHub Pages 설정
1. 저장소 push 후 **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**.
2. workflow의 `contents: write` 권한으로 생성 결과가 자동 커밋/배포된다.

## Kiwoom (매매일지 자동 기록)
키움 OpenAPI+ OCX는 **Windows 32-bit Python + KOA Studio** 설치 환경 필요.
`python -m app.main` → 로그인 → 동기화 → `data/trades/trades.json` 갱신 → push 시 대시보드 재생성.

> 정보·참고용 도구이며 투자 판단의 책임은 본인에게 있습니다.
