"""Tests for relay structured logging module."""

import json
import logging
import sys


from relay.app.logging import CloudJsonFormatter, RelayEnv, configure_logging


class TestCloudJsonFormatter:
    """Tests for the CloudJsonFormatter class."""

    def _make_record(
        self,
        message: str,
        level: int,
        logger_name: str,
    ) -> logging.LogRecord:
        """Create a LogRecord for testing."""
        record = logging.LogRecord(
            name=logger_name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    def test_json_formatter_output(self) -> None:
        """CloudJsonFormatter produces valid JSON with severity, message, logger fields."""
        formatter = CloudJsonFormatter()
        record = self._make_record("test message", logging.INFO, "relay.test")
        output = formatter.format(record)

        parsed = json.loads(output)
        assert parsed["severity"] == "INFO"
        assert parsed["message"] == "test message"
        assert parsed["logger"] == "relay.test"

    def test_severity_mapping_info(self) -> None:
        """Python INFO maps to Cloud Logging INFO."""
        formatter = CloudJsonFormatter()
        record = self._make_record("info msg", logging.INFO, "test")
        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "INFO"

    def test_severity_mapping_warning(self) -> None:
        """Python WARNING maps to Cloud Logging WARNING."""
        formatter = CloudJsonFormatter()
        record = self._make_record("warn msg", logging.WARNING, "test")
        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "WARNING"

    def test_severity_mapping_error(self) -> None:
        """Python ERROR maps to Cloud Logging ERROR."""
        formatter = CloudJsonFormatter()
        record = self._make_record("error msg", logging.ERROR, "test")
        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "ERROR"

    def test_json_formatter_includes_stack_trace(self) -> None:
        """When logging an exception, stack_trace field is present."""
        formatter = CloudJsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            record = self._make_record("error occurred", logging.ERROR, "test")
            record.exc_info = sys.exc_info()

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "stack_trace" in parsed
        assert "ValueError: boom" in parsed["stack_trace"]


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def _cleanup_root_logger(self) -> None:
        """Remove all handlers from root logger."""
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        root.setLevel(logging.WARNING)

    def test_dev_formatter(self) -> None:
        """configure_logging(RelayEnv.DEVELOPMENT) produces human-readable format."""
        self._cleanup_root_logger()
        configure_logging(RelayEnv.DEVELOPMENT)

        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        # Development format should NOT be CloudJsonFormatter
        assert not isinstance(handler.formatter, CloudJsonFormatter)
        # Verify it uses a standard format string
        assert handler.formatter is not None
        assert "%(levelname)" in handler.formatter._fmt

        self._cleanup_root_logger()

    def test_production_formatter(self) -> None:
        """configure_logging(RelayEnv.PRODUCTION) produces JSON format."""
        self._cleanup_root_logger()
        configure_logging(RelayEnv.PRODUCTION)

        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, CloudJsonFormatter)

        self._cleanup_root_logger()

    def test_uvicorn_access_log_suppressed(self) -> None:
        """After configure_logging(), uvicorn.access logger has no handlers and propagate=False."""
        self._cleanup_root_logger()
        configure_logging(RelayEnv.PRODUCTION)

        access_logger = logging.getLogger("uvicorn.access")
        assert access_logger.handlers == []
        assert access_logger.propagate is False

        self._cleanup_root_logger()
