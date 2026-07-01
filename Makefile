COMPOSE = docker compose -f infra/compose/docker-compose.yml --env-file .env

.PHONY: up down build logs migrate makemigration seed test fmt sh-api

up:            ## 빌드 + 기동 (백그라운드)
	$(COMPOSE) up -d --build

down:          ## 중지 + 볼륨 유지
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f api

migrate:       ## Alembic 마이그레이션 적용
	$(COMPOSE) exec api alembic upgrade head

makemigration: ## 새 마이그레이션 생성 (m="메시지")
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

seed:          ## data_provider_source + 샘플 instrument 시드
	$(COMPOSE) exec api python -m scripts.seed

test:          ## pytest
	$(COMPOSE) exec api pytest -q

fmt:
	$(COMPOSE) exec api ruff format app tests

sh-api:
	$(COMPOSE) exec api bash
