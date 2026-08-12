"""
Structured Logging Configuration — structlog + python-json-logger
Provides consistent JSON logging across the entire application.
"""

import logging
import sys
from typing import Any

import structlog
from app.core.config import settings


def configure_logging() -> None:
    """
    Configure structlog for structured JSON logging.
    In DEBUG mode, uses human-readable console renderer.
    In production, uses JSON renderer for log aggregation tools.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Suppress noisy third-party loggers
    for logger_name in ["uvicorn.access", "httpx", "motor"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Determine renderer based on format setting
    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        renderer,
    ]

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a named structlog logger.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured bound logger instance.
    """
    return structlog.get_logger(name)
