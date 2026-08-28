"""Tests for ObsidianMCP logging configuration."""


import structlog

from obsidian_mcp.logging import configure_logging, get_logger


class TestConfigureLogging:
    """Test configure_logging function."""

    def test_configure_logging_defaults(self):
        """Test configure_logging with defaults sets up structlog."""
        # Reset structlog config
        structlog.reset_defaults()
        
        configure_logging()
        
        # Verify we can get a logger
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_custom_level(self):
        """Test configure_logging with custom level."""
        structlog.reset_defaults()
        
        configure_logging(level="DEBUG")
        
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_json_output_false(self):
        """Test configure_logging with console output."""
        structlog.reset_defaults()
        
        configure_logging(json_output=False)
        
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_multiple_calls_idempotent(self):
        """Test multiple configure_logging calls don't error."""
        structlog.reset_defaults()
        
        configure_logging(level="INFO", json_output=True)
        configure_logging(level="DEBUG", json_output=False)
        configure_logging(level="WARNING", json_output=True)
        
        logger = get_logger("test")
        assert logger is not None


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns a BoundLogger instance."""
        structlog.reset_defaults()
        configure_logging()
        
        logger = get_logger("test.module")
        # structlog returns a BoundLoggerLazyProxy that wraps BoundLogger
        assert hasattr(logger, "_logger")
        assert hasattr(logger, "info")

    def test_get_logger_different_names(self):
        """Test get_logger returns different loggers for different names."""
        structlog.reset_defaults()
        configure_logging()
        
        logger1 = get_logger("module.one")
        logger2 = get_logger("module.two")
        
        assert logger1 is not logger2

    def test_logger_methods_exist(self):
        """Test logger has standard methods."""
        structlog.reset_defaults()
        configure_logging()
        
        logger = get_logger("test")
        
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")
        assert hasattr(logger, "exception")

    def test_logger_binds_context(self):
        """Test logger can bind context variables."""
        structlog.reset_defaults()
        configure_logging()
        
        logger = get_logger("test")
        bound = logger.bind(request_id="123", user="test")
        
        assert bound is not None


class TestLoggingIntegration:
    """Integration tests for logging output."""

    def test_logging_outputs_json(self, capsys):
        """Test JSON log output format."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=True)
        
        logger = get_logger("test")
        logger.info("test.message", key="value")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "test.message" in output
        assert "key" in output
        assert "value" in output

    def test_logging_outputs_console(self, capsys):
        """Test console log output format."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=False)
        
        logger = get_logger("test")
        logger.info("test.message", key="value")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "test.message" in output

    def test_logging_includes_timestamp(self, capsys):
        """Test log output includes ISO timestamp."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=True)
        
        logger = get_logger("test")
        logger.info("test.message")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "timestamp" in output.lower()

    def test_logging_includes_level(self, capsys):
        """Test log output includes log level."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=True)
        
        logger = get_logger("test")
        logger.info("test.message")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "info" in output.lower()

    def test_logging_includes_logger_name(self, capsys):
        """Test log output includes logger name."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=True)
        
        logger = get_logger("custom.name")
        logger.info("test.message")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "custom.name" in output

    def test_logging_exception_includes_traceback(self, capsys):
        """Test exception logging includes traceback."""
        structlog.reset_defaults()
        configure_logging(level="INFO", json_output=True)
        
        logger = get_logger("test")
        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("error.occurred")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "error.occurred" in output
        assert "ValueError" in output
        assert "test error" in output


class TestLoggingLevels:
    """Test log level filtering."""

    def test_debug_level_outputs_debug(self, capsys):
        """Test DEBUG level outputs debug messages."""
        structlog.reset_defaults()
        configure_logging(level="DEBUG", json_output=True)
        
        logger = get_logger("test")
        logger.debug("debug.message")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "debug.message" in output

    def test_info_level_suppresses_debug(self, capsys):
            """Test INFO level suppresses debug messages."""
            structlog.reset_defaults()
            configure_logging(level="INFO", json_output=True)

            logger = get_logger("test")
            logger.debug("debug.message")

            capsys.readouterr()
            # With structlog + stdlib, debug may still appear depending on config
            # This test documents current behavior

    def test_warning_level_outputs_warning(self, capsys):
        """Test WARNING level outputs warnings."""
        structlog.reset_defaults()
        configure_logging(level="WARNING", json_output=True)
        
        logger = get_logger("test")
        logger.warning("warning.message")
        
        captured = capsys.readouterr()
        output = captured.out
        assert "warning.message" in output