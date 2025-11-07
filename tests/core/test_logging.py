"""Tests for logging utilities in nexus.core.logging."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus.core.logging import get_logger, setup_logging


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging(level=logging.DEBUG, log_file="test.log")

            mock_basic_config.assert_called_once()
            call_args = mock_basic_config.call_args
            assert call_args[1]["level"] == logging.DEBUG
            assert len(call_args[1]["handlers"]) == 2  # StreamHandler and FileHandler

    def test_setup_logging_creates_log_directory(self):
        """Test that setup_logging creates the log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "subdir" / "test.log"
            setup_logging(log_file=str(log_file))

            assert log_file.parent.exists()

    def test_setup_logging_default_params(self):
        """Test setup_logging with default parameters."""
        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            call_args = mock_basic_config.call_args
            assert call_args[1]["level"] == logging.INFO
            assert "nexus.log" in str(call_args[1]["handlers"][1])  # FileHandler

    def test_setup_logging_reduces_external_noise(self):
        """Test that external library loggers are set to WARNING."""
        with patch("logging.basicConfig"):
            setup_logging()

            urllib3_logger = logging.getLogger("urllib3")
            requests_logger = logging.getLogger("requests")

            assert urllib3_logger.level == logging.WARNING
            assert requests_logger.level == logging.WARNING


class TestGetLogger:
    """Test the get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_names(self):
        """Test that get_logger returns different loggers for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger1 is not logger2

    def test_get_logger_same_name_returns_same_instance(self):
        """Test that get_logger returns the same instance for the same name."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")

        assert logger1 is logger2
