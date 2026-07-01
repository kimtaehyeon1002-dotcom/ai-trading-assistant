"""구조화 로깅 (structlog). 뉴스 본문·PII는 적재하지 않는다."""
from __future__ import annotations

import logging

import structlog

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=settings.log_level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "thbot") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
