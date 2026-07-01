# 호스트 파이썬 버전과 무관하게 컨테이너는 3.12 사용
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# 빌드 의존성 (asyncpg/psycopg 등 일부 휠 보강용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (레이어 캐시)
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# 소스 (compose 볼륨 마운트로 핫리로드 시 덮어씀)
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
