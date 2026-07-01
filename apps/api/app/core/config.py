"""애플리케이션 설정 (환경변수 → Pydantic Settings)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    # DB / cache
    database_url: str = "postgresql+asyncpg://thbot:thbot@db:5432/thbot"
    redis_url: str = "redis://redis:6379/0"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 14

    # Anthropic
    anthropic_api_key: str | None = None

    # Voyage (RAG 임베딩) — voyage-3.5 1024D 고정(설계서 §5.2)
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3.5"
    voyage_base_url: str = "https://api.voyageai.com/v1/embeddings"
    embed_dim: int = 1024
    # RAG 고도화(Phase 6): rerank·하이브리드
    voyage_rerank_url: str = "https://api.voyageai.com/v1/rerank"
    voyage_rerank_model: str = "rerank-2.5"
    rag_use_rerank: bool = True

    # 과금/쿼터(Phase 7)
    default_plan: str = "free"

    # Notion (매매일지 임포트) — 백엔드 내부 integration 토큰 필요(MCP 커넥터와 별개)
    notion_api_key: str | None = None
    notion_version: str = "2022-06-28"
    notion_base_url: str = "https://api.notion.com/v1"
    # 매매 일지 _ 쉽알남 DB (데이터소스 collection://fb9dbad2-41f8-832d-837f-873abc14def8)
    notion_journal_database_id: str | None = "594dbad241f883f0b40481906cd4b123"

    # Scheduler (APScheduler 인프로세스) — 모닝리포트 06:30 / 테마 06:00 KST
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Asia/Seoul"

    # 모닝리포트 기준값(사용자 설정) — 평일 지정시각 1회 생성
    morning_enabled: bool = True
    morning_hour: int = 6  # KST
    morning_minute: int = 30
    morning_markets: str = "US,KR"  # 콤마 구분
    morning_style: str = "swing"  # scalping | swing | long (테마 호라이즌 가중)
    morning_top_themes: int = 5  # 시장별 상위 테마 수
    morning_min_theme_score: float = 0.0  # 이 점수 미만 테마 제외(0=전부)
    morning_use_opus: bool = False  # 비용 최소화: 기본 Sonnet 합성(True면 Opus 심층)

    # 비용 절감 노브(혼자 쓰기 최적화)
    llm_prompt_cache: bool = True  # 시스템 프리픽스 프롬프트 캐싱(입력비 0.1x)
    research_cache_same_day: bool = True  # 같은 종목·질문·당일 리포트 재사용(LLM 0원)
    rag_top_k: int = 4  # 합성에 넣는 RAG 청크 수(작을수록 입력비↓)

    @property
    def morning_markets_list(self) -> list[str]:
        return [m.strip().upper() for m in self.morning_markets.split(",") if m.strip()]

    # CORS (콤마 구분)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        """Alembic용 동기 드라이버 URL (asyncpg → psycopg)."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
