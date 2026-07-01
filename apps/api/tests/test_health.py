"""/healthz 스모크 — DB 없이 동작(라이브니스)."""
from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    with TestClient(app) as client:
        res = client.get("/api/v1/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_openapi_has_core_routes():
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/market/quotes/{instrument_id}" in paths
        assert "/api/v1/debug/claude-ping" in paths
