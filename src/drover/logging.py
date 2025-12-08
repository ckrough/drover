"""Structured logging configuration for Drover.

Provides consistent JSON-formatted logging for LLM operations,
classification events, and error tracking.
"""

import logging
import sys

import structlog

from drover.config import LogLevel


def configure_logging(
    level: LogLevel = LogLevel.QUIET,
    json_output: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level from config (QUIET, VERBOSE, DEBUG).
        json_output: If True, output JSON format; otherwise console format.
    """
    # Map LogLevel to Python logging levels
    level_map = {
        LogLevel.QUIET: logging.WARNING,
        LogLevel.VERBOSE: logging.INFO,
        LogLevel.DEBUG: logging.DEBUG,
    }
    log_level = level_map.get(level, logging.WARNING)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
        force=True,
    )

    # Suppress noisy third-party loggers (pdfminer, unstructured, etc.)
    # pdfminer.six outputs verbose debug info (nexttoken, do_keyword, etc.)
    noisy_loggers = [
        "pdfminer",
        "pdfminer.pdfpage",
        "pdfminer.pdfinterp",
        "pdfminer.converter",
        "pdfminer.cmapdb",
        "pdfminer.psparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfparser",
        "unstructured",
        "PIL",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    # Build processor chain
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger for the given module name.

    Args:
        name: Module name (typically __name__).

    Returns:
        Configured structured logger.
    """
    return structlog.get_logger(name)
