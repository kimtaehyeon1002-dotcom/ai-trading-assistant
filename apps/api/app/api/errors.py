"""예외 → ProblemDetail(JSON) 매핑. (설계서 §7.1)"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.data_providers.errors import RateLimitError, SourceUnavailable

log = get_logger("api")

_STATUS_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL",
    503: "SOURCE_UNAVAILABLE",
}


def _problem(status_code: int, title: str, detail: str | None, code: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://th-bot/errors/{(code or _STATUS_CODE.get(status_code, 'ERROR')).lower()}",
            "title": title,
            "status": status_code,
            "code": code or _STATUS_CODE.get(status_code, "ERROR"),
            "detail": detail,
            "request_id": str(uuid.uuid4()),
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _problem(exc.status_code, str(exc.detail), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _problem(422, "Validation Failed", str(exc.errors()), "VALIDATION_ERROR")

    @app.exception_handler(RateLimitError)
    async def _ratelimit(_: Request, exc: RateLimitError):
        return _problem(429, "Rate Limited", str(exc), "RATE_LIMITED")

    @app.exception_handler(SourceUnavailable)
    async def _source(_: Request, exc: SourceUnavailable):
        return _problem(503, "Data Source Unavailable", str(exc), "SOURCE_UNAVAILABLE")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("unhandled_exception", error=str(exc))
        return _problem(500, "Internal Server Error", "unexpected error", "INTERNAL")
