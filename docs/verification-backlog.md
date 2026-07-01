# 검증 백로그 (런타임 미검증 항목)

> 이 환경 제약: **Docker 없음 · Node 없음 · psql/uv 없음 · Python 3.14.** (단, **pip + 네트워크는 가용**)

## ✅ 런타임 검증 결과 (2026-06-24 세션 — host venv)
pip로 venv를 만들어 pydantic/sqlalchemy/pgvector/fastapi/bcrypt/redis 등 순수파이썬 의존성을 설치하고 실제로 실행 검증함(Postgres/asyncpg는 sqlite+aiosqlite URL로 우회 — 임포트/구성 검증용, DB 연결 테스트는 제외):
- **`pytest tests/` → 98 passed** (compliance/redlist 누설0, normalization, theme_scoring, journal_metrics, coach, portfolio, rag_advanced, billing, claude 스텁, research 스텁 스트림, rag chunking/embeddings, security, health TestClient, providers 계약).
- **FastAPI 앱 실제 구성 성공**: `create_app()` + OpenAPI 스키마 생성, **/api/v1 34개 라우트 전부 등록**(research/notes·reports/themes·journal/coach·portfolio/analyze·usage 포함).
- **전 모듈·4개 파이프라인·rag_service 런타임 임포트 OK**(정적 분석을 넘어 실증, 순환 없음).
- 🐞 **수정**: runtime 검증이 dep 호환성 버그를 발견 — `passlib 1.7`(미유지보수)이 `bcrypt 4.1+`와 비호환(>72B 자체프로브에서 ValueError). → `core/security.py`를 **bcrypt 직접 사용**으로 교체(72B 절단), pyproject에서 passlib 제거. 재실행 시 test_security 통과.

## 아직 런타임 미검증(인프라 필요) — Postgres+pgvector / Redis / Next.js / 실제 외부 API
> 아래는 **Docker/Postgres 환경 + 실제 키(ANTHROPIC/VOYAGE/NOTION)** 가 있어야 검증 가능. `alembic upgrade head`(0001~0007) 후 점검.

## Phase 0~1 (기반/데이터 추상화)
- [ ] `docker compose up -d` → `/healthz`·`/readyz` 200 (DB/Redis 연결)
- [ ] `alembic upgrade head` (0001) → 테이블 + `vector` 확장 생성, seed(`data_provider_source`, 삼성전자/AAPL)
- [ ] `POST /auth/login` → JWT 발급, `GET /auth/me`
- [ ] `GET /market/quotes/{id}` → 무료 어댑터 정규화 응답(source/is_realtime/as_of)
- [ ] Provider 어댑터 실제 데이터 수집(yfinance/fdr/rss) — 네트워크 의존
- [ ] `/debug/claude-ping` → `agent_run` 적재(ANTHROPIC_API_KEY 있을 때 실호출, 없으면 stub)
- [ ] web 로그인 → 대시보드 렌더(Next.js 빌드/런타임)

## Phase 2 (AI Research) — 이번 구현
- [ ] `alembic upgrade head` (0002) → `research_report` 테이블 생성
- [ ] `POST /research/jobs` → 202 `{job_id, stream_url, result_url}`
- [ ] `GET /research/jobs/{id}/stream` SSE end-to-end: stage/tool/token/done 수신
- [ ] `GET /research/jobs/{id}` 폴링 상태 전이(pending→running→completed)
- [ ] `GET /research/results/{id}` 멱등 재조회(job_id 인메모리 + report_id 영속 양쪽)
- [ ] `JobManager` asyncio 백그라운드 태스크 실동작 + 큐 소비/종료(_DONE)
- [ ] DB 영속화: `research_report`(blocks/citations/intent JSONB) 저장·재조립
- [ ] 실제 Claude 스트리밍(`messages.stream`) + usage 토큰 집계 → `cost_usd`
- [ ] 2차 LLM 분류기(`compliance/classifier.py`) 실제 Haiku 호출 경로
- [ ] `pytest tests/` 전체(특히 `test_research.py`) — pydantic/sqlalchemy 필요
- [ ] `get_candles("1d")`를 실제 provider가 지원하는지(미지원 시 ProviderError 폴백 경로)
- [ ] 프론트 `research/page.tsx` EventSource 연결 + `API_ORIGIN` 경로 결합 렌더
- [ ] **레드리스트 50~100개 회귀 테스트**(설계서 §10.1) — 스트리밍 경로 "전송 전 차단" 누설률 0 (미작성)

## Phase 2.5 (최소 RAG) — 이번 구현
- [ ] `alembic upgrade head` (0003) → `rag_document`/`rag_chunk` 생성, `vector(1024)` 컬럼 + HNSW/GIN 인덱스
- [ ] `POST /debug/rag-ingest-news`(admin) → 뉴스 제목+요약 인입(본문 미저장), content_hash dedup
- [ ] `python -m scripts.ingest_news_rag [KR|US] [limit]` 배치 인입
- [ ] `rag_service.search` 벡터 ANN(cosine) + 권한(is_public/owner/license_ok)·메타(symbols/market/doc_type/since) 필터 + `SET LOCAL hnsw.ef_search`
- [ ] 리서치 파이프라인 gather에 `rag_search` 연결 → `ctx["rag"]` + 인용 번호 뉴스 뒤로 이어붙임 + `tool` 이벤트
- [ ] 실제 Voyage 임베딩(`VOYAGE_API_KEY`): input_type document/query, 1024D 일치(스텁은 결정적 의사벡터)
- [ ] `content_tsv = to_tsvector('simple', content)` 채움 + GIN(Phase 6 BM25 대비)
- [ ] `list[float]` → pgvector `Vector` 바인딩/`cosine_distance` 동작(pgvector 확장 필요)
- [ ] `pytest tests/test_rag.py` 전체(embeddings/_source_label 포함)

## Phase 3 (모닝리포트 + Theme Scoring) — 이번 구현
- [ ] `alembic upgrade head` (0004) → `theme`/`theme_membership`/`theme_score`/`morning_report` 생성
- [ ] `python -m scripts.seed` → 테마(us-bigtech/AAPL, kr-semiconductor/005930) + membership 적재
- [ ] APScheduler 기동: 앱 lifespan에서 start_scheduler(평일 06:00 테마 / 06:30 모닝리포트, KST). `apscheduler` 설치 필요
- [ ] `compute_theme_scores`(시장별) → 구성종목 `get_candles` 수집(네트워크) → `theme_score` 적재
- [ ] `POST /reports/generate`(admin, 202) → 백그라운드 모닝리포트 생성(멱등: report_date+scope+ver)
- [ ] `GET /reports`·`/reports/{id}`·`/reports/by-date/{date}`·`/reports/themes?market=&timeframe=`
- [ ] 모닝리포트 합성: 실제 Opus(`MORNING_REPORT`) 또는 스텁 5-섹션 → 가드레일 통과 + 면책
- [ ] `get_latest_scores`(max as_of 배치) 정확성 + `get_theme_scores` 툴 노출
- [ ] 프론트 `reports/page.tsx`(날짜 조회·테마 리스트·admin 생성)
- [ ] `pytest tests/test_theme_scoring.py` 전체

## Phase 4 (매매일지 + Trading Coach, Notion 연동) — 이번 구현
- [ ] **백엔드 Notion 통합 토큰 설정**(MCP 커넥터와 별개): Notion 내부 integration 생성 → '매매 일지 _ 쉽알남' DB 공유 → `NOTION_API_KEY` + `NOTION_JOURNAL_DATABASE_ID`(기본값 594dbad2…) 설정. ※ MCP 커넥터의 행 일괄조회는 Business 플랜 전용이라 막혀서 REST API 토큰 경로로 구현함
- [ ] `alembic upgrade head` (0005) → `trade_journal_entry` 생성
- [ ] `POST /journal/import` → Notion REST `databases/{id}/query` 실제 조회 → 멱등 적재(source_row_id). 토큰 없으면 스텁 7건
- [ ] Notion `_map_row` 실제 응답 매핑(select 종목명/포지션·checkbox 승무패·number 수익금·date 날짜·title 복기)
- [ ] `GET /journal/entries`·`GET /journal/metrics`(코드 계산, LLM 비의존)
- [ ] `POST /journal/coach` → Sonnet(JOURNAL_ANALYSIS) 또는 스텁 → 가드레일 통과 + 면책, "지금 다시 살까?" 교육 라우팅
- [ ] 프론트 `journal/page.tsx`(임포트·지표 대시보드·코치)
- [ ] `pytest tests/test_journal.py` 전체
- (후속) CSV/이미지·PDF 멀티모달 임포트(구조화 스키마만 수용)는 Notion 경로 이후로 이연

## Phase 5 (포트폴리오 AI) — 이번 구현
- [ ] `alembic upgrade head` (0006) → `portfolio`/`holding` 생성
- [ ] `POST /portfolio/holdings`(종목 해소·upsert) · `GET /portfolio/holdings`(평가) · `DELETE /portfolio/holdings/{id}`
- [ ] `GET /portfolio/metrics` — 비중·HHI·유효종목수·섹터/시장/통화 노출(코드 계산)
- [ ] 다통화 평가: `get_quote`×수량 → `get_fx(USD,KRW)`로 기준통화 환산(시세 미수집 시 평단가 폴백·플래그)
- [ ] `POST /portfolio/analyze` → Sonnet(PORTFOLIO_ANALYSIS) 또는 스텁 4블록 → 가드레일 통과 + 면책, 리밸런싱/매매 지시 없음
- [ ] 프론트 `portfolio/page.tsx`(보유 추가/삭제·지표·분석)
- [ ] `pytest tests/test_portfolio.py` 전체

## Phase 6 (RAG 고도화) — 이번 구현
- [ ] 하이브리드 검색: `store.keyword_search`(tsvector @@ websearch_to_tsquery) + `vector_search` → `retrieve.hybrid_search`(RRF→rerank→시간가중)
- [ ] Voyage `rerank-2.5` 실제 호출(VOYAGE_API_KEY) — 키 없으면 토큰겹침 스텁
- [ ] `content_tsv` GIN 인덱스로 BM25 동작(0003에서 생성)
- [ ] 개인 노트 인입 `POST /research/notes`(owner_user_id·is_public=false) → 본인만 검색(RLS 격리) 실데이터 확인
- [ ] faithfulness LLM-judge(Haiku) 실호출 경로 + 임계 차단
- [ ] `pytest tests/test_rag_advanced.py`, `tests/test_compliance_redlist.py`(레드리스트 32건 누설 0)

## Phase 7 (멀티유저 + 과금) — 이번 구현
- [ ] `alembic upgrade head` (0007) → `user.plan` 컬럼; `python -m scripts.seed`로 owner=enterprise
- [ ] `GET /usage` → 일일 LLM 비용(agent_run 집계)·잔여 한도
- [ ] 쿼터 강제: `POST /research/jobs`에서 한도 초과 429, 심층 한도부족 시 표준 강등(실 비용 누적 후 동작 확인)
- [ ] `usage_service.spent_today` agent_run 합계(타임존 일 경계) 정확성
- [ ] Celery 전환(선택): `app/workers/celery_app.py`/`tasks.py` 워커 기동(celery+redis), beat로 APScheduler 대체
- [ ] `pytest tests/test_billing.py`

## 이미 오프라인 검증된 것(참고)
- `compileall`(app/tests/migrations/scripts) 통과, app.* 임포트 그래프 정적 해소 OK(순환 없음)
- 스트리밍 게이트: 위반 문장만 치환·정상 통과, 치환 표지가 최종 풀검증을 막지 않음(이중차단 방지)
- 스텁 4-블록 마크다운 가드레일 통과 + 4블록 파싱, 매매결정 의도 감지, 스텁 스트림 재구성
- RAG: 청킹(단일/장문 분할·헤더 주입), 스텁 임베딩(1024D·결정적·단위벡터), 인용 source 라벨
- **Theme Scoring**: 강/약 테마 순위 분리·점수 단조, robust z-score(순위 보존), winsorize(작은 N 무클램프), 스타일 가중 합=1, 결측 중립
- **모닝리포트 스텁**: 5-섹션 가드레일 통과(+면책), "매수 신호"→"투자 권유" 리워딩으로 buy_sell 오탐 차단
- **매매 메트릭**: 승률·손익비·기대값·MDD·연속손실·포지션/종목/요일 분해, 빈 입력 안전(None/0)
- **Trading Coach 스텁**: 4블록 가드레일 통과(+면책), 매매결정 질문 교육 라우팅, 포지션 롱/숏 한글화로 LONG/SHORT 오탐 차단
- **포트폴리오 메트릭**: HHI·유효종목수·집중도 밴드(높음/보통/낮음)·상위 비중·섹터/시장/통화 노출, 빈 입력 안전
- **포트폴리오 분석 스텁**: 4블록 가드레일 통과(+면책), 리밸런싱/매매 지시 없음(분산 관점 관찰만)
- **RAG 고도화**: RRF 융합, 시간가중(doctype/style별 감쇠·음수 클램프·단조), rerank 스텁(토큰겹침), Recall@k·MRR
- **컴플라이언스 회귀(§10.1)**: 레드리스트 32건 누설률 0 + 교육 5건 오탐 0
- **쿼터 결정**: 한도초과 block / 정상 allow / 심층 한도부족·플랜 제한 downgrade

## (이후 Phase에서 추가 예정)
- Phase 4 일지·코치 / Phase 5 포트폴리오 / Phase 6 RAG 고도화 / Phase 7 멀티유저·과금 런타임 항목은 구현 시 누적.
