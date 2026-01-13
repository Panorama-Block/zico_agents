"""
Structured Logging Configuration.

Supports:
- Color output for development (colorlog)
- JSON output for production (structlog)
"""

import logging
import os
import sys
from typing import Literal

LogFormat = Literal["color", "json"]


def setup_logging(
    level: int | str = logging.INFO,
    format_type: LogFormat | None = None,
    json_indent: int | None = None,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ("color" for dev, "json" for prod)
                    If None, reads from LOG_FORMAT env var (defaults to "color")
        json_indent: Indentation for JSON output (None for compact)

    Returns:
        Configured root logger
    """
    # Determine format from env if not specified
    if format_type is None:
        format_type = os.getenv("LOG_FORMAT", "color").lower()
        if format_type not in ("color", "json"):
            format_type = "color"

    # Parse level if string
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if format_type == "color":
        formatter = _create_color_formatter()
    else:
        formatter = _create_json_formatter(json_indent)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langsmith").setLevel(logging.WARNING)

    return root_logger


def _create_color_formatter() -> logging.Formatter:
    """Create colorized formatter for development."""
    try:
        import colorlog

        return colorlog.ColoredFormatter(
            fmt="%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            secondary_log_colors={},
            style="%",
        )
    except ImportError:
        # Fallback if colorlog not installed
        return logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def _create_json_formatter(indent: int | None = None) -> logging.Formatter:
    """Create JSON formatter for production."""
    try:
        import structlog

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(indent=indent),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Return a simple formatter since structlog handles formatting
        return logging.Formatter("%(message)s")

    except ImportError:
        # Fallback JSON formatter
        import json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        return JsonFormatter()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(
                f"{self.__class__.__module__}.{self.__class__.__name__}"
            )
        return self._logger
