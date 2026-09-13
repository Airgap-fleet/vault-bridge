"""Structured logging configuration for Obsidian MCP."""

import logging
import sys
from typing import cast

import structlog
from structlog.stdlib import BoundLogger, LoggerFactory


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog for structured JSON logging to stderr only."""

    # Remove existing handlers to allow reconfiguration (important for tests)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # CRITICAL FIX: Use stderr, NOT stdout. MCP protocol reserves stdout for JSON-RPC messages only.
    # Logging to stdout corrupts the handshake and breaks client parsing.
    handler = logging.StreamHandler(sys.stderr)
    
    if json_output:
        formatter = logging.Formatter(fmt="%(message)s")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Add NullHandler to prevent "No handlers could be found" warnings from library code
    logging.getLogger().addHandler(logging.NullHandler())

    # Configure structlog processors
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
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
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Get a structured logger instance."""
    return cast(BoundLogger, structlog.get_logger(name))
