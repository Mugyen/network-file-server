"""Structured logging for the relay server.

Provides a JSON formatter for Cloud Logging integration and a configuration
function to switch between development (human-readable) and production (JSON)
log output.
"""

import json
import logging
import sys
import traceback
from enum import Enum


class RelayEnv(str, Enum):
    """Runtime environment for the relay server."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"


# Maps Python log level names to Cloud Logging severity values.
_SEVERITY_MAP: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}

# Human-readable log format for development mode.
_DEV_FORMAT = "%(levelname)-8s %(name)s: %(message)s"


class CloudJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for Cloud Logging.

    Each line contains at minimum: severity, message, logger.
    When exc_info is present, a stack_trace field is included.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a LogRecord as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string with severity, message, and logger fields.
        """
        entry: dict[str, object] = {
            "severity": _SEVERITY_MAP.get(record.levelname, record.levelname),
            "message": record.getMessage(),
            "logger": record.name,
        }

        if record.exc_info and record.exc_info[0] is not None:
            entry["stack_trace"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        return json.dumps(entry, default=str)


def configure_logging(env: RelayEnv) -> None:
    """Configure the root logger for the specified environment.

    - Clears all existing root handlers.
    - Sets root level to INFO.
    - Adds a StreamHandler(stdout) with CloudJsonFormatter (production)
      or a standard text formatter (development).
    - Suppresses uvicorn.access logger (clears handlers, propagate=False).

    Args:
        env: The relay environment — determines formatter selection.
    """
    root = logging.getLogger()

    # Clear existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if env == RelayEnv.PRODUCTION:
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_DEV_FORMAT))

    root.addHandler(handler)

    # Suppress uvicorn access logs — we use app-level structured logging
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
