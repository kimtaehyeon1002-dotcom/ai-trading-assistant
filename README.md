# Th_bot — AI 투자 리서치 / 비서 플랫폼

투자 **판단 보조** 플랫폼. 매수/매도 추천·목표주가·매매 시그널을 생성하지 않으며, 모든 LLM 출력은
정보/분석/시나리오/리스크 + 면책 고지로 제한된다(자본시장법 컴플라이언스). 상세 설계는
`C:\Users\1\.claude\plans\ai-cached-rossum.md` 참조.

## 현재 구현 범위 (Phase 0 + Phase 1)

- **Phase 0 기반:** Docker Compose 로컬 스택(FastAPI · PostgreSQL+pgvector · Redis · Next.js),
  JWT 인증, 핵심 테이블(`user`/`auth_credential`/`instrument`/`data_provider_source`/`agent_run`),
  Claude API 래퍼(모델 라우팅 + `agent_run` 비용 로깅).
- **Phase 1 데이터 추상화:** Provider 인터페이스(Quote/Financials/News/FX) + 무료 어댑터
  (FinanceDataReader·pykrx=KR, yfinance=US, RSS=뉴스) + 정규화 스키마 + 폴백 레지스트리.
- **Phase 2 연결 자리:** `app/agents/{tools,prompts,pipelines}`, `app/compliance`, `app/rag`,
  `api/v1/research.py`(스텁)가 이미 골격으로 존재.

## 빠른 시작 (Docker 필요)

```bash
cp .env.example .env          # 값 채우기 (특히 JWT_SECRET, ANTHROPIC_API_KEY)
make up                       # docker compose 빌드 + 기동
make migrate                  # Alembic 마이그레이션 (pgvector 확장 + 테이블)
make seed                     # data_provider_source + 샘플 instrument 시드
# API:  http://localhost:8000  (docs: /docs, health: /healthz)
# Web:  http://localhost:3000
```

## 검증

```bash
make test                     # pytest (auth, provider 정규화 계약)
# 1) GET /healthz, /readyz           → 200
# 2) POST /api/v1/auth/login         → JWT 발급, GET /api/v1/auth/me
# 3) GET /api/v1/market/quotes/{id}  → 무료 어댑터 정규화 응답(source/is_realtime/data_delay_sec/as_of)
# 4) Claude 래퍼 Haiku ping          → agent_run row(model/tokens/cost/latency) 적재
```

> 이 머신에 Docker/Node가 없으면 위 스택 기동은 해당 도구 설치 후 실행한다.
> 백엔드 구문 점검만은 `python -m compileall apps/api/app`로 가능.

## 구조

```
apps/api   FastAPI 백엔드 (app/{api,agents,compliance,services,data_providers,rag,models,schemas,scheduler,workers,core})
apps/web   Next.js 프론트 (반응형 웹)
infra      docker compose / Dockerfile / env 템플릿
scripts    seed / backfill
```
