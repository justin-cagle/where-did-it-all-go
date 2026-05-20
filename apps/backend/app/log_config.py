"""Configure stdlib logging + structlog from application settings."""

import logging

import structlog


def configure_logging(log_level: str = "INFO", *, debug: bool = False) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", level=level)

    # Quieten noisy third-party loggers in production.
    if not debug:
        for noisy in ("uvicorn.access", "sqlalchemy.engine"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
