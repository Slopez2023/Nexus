"""Tests for custom exceptions in nexus.core.exceptions."""

import unittest

from nexus.core.exceptions import (
    ConfigurationError,
    DataError,
    ExecutionError,
    NexusError,
    RiskError,
    StrategyError,
    ValidationError,
)


class TestNexusError(unittest.TestCase):
    """Test the base NexusError exception."""

    def test_nexus_error_inheritance(self):
        """Test that NexusError inherits from Exception."""
        self.assertTrue(issubclass(NexusError, Exception))

    def test_nexus_error_raises(self):
        """Test that NexusError can be raised."""
        with self.assertRaises(NexusError):
            raise NexusError("Test error")


class TestDataError(unittest.TestCase):
    """Test the DataError exception."""

    def test_data_error_inheritance(self):
        """Test that DataError inherits from NexusError."""
        self.assertTrue(issubclass(DataError, NexusError))

    def test_data_error_raises(self):
        """Test that DataError can be raised."""
        with self.assertRaises(DataError):
            raise DataError("Data fetch failed")


class TestConfigurationError(unittest.TestCase):
    """Test the ConfigurationError exception."""

    def test_configuration_error_inheritance(self):
        """Test that ConfigurationError inherits from NexusError."""
        self.assertTrue(issubclass(ConfigurationError, NexusError))

    def test_configuration_error_raises(self):
        """Test that ConfigurationError can be raised."""
        with self.assertRaises(ConfigurationError):
            raise ConfigurationError("Config validation failed")


class TestStrategyError(unittest.TestCase):
    """Test the StrategyError exception."""

    def test_strategy_error_inheritance(self):
        """Test that StrategyError inherits from NexusError."""
        self.assertTrue(issubclass(StrategyError, NexusError))

    def test_strategy_error_raises(self):
        """Test that StrategyError can be raised."""
        with self.assertRaises(StrategyError):
            raise StrategyError("Strategy execution failed")


class TestRiskError(unittest.TestCase):
    """Test the RiskError exception."""

    def test_risk_error_inheritance(self):
        """Test that RiskError inherits from NexusError."""
        self.assertTrue(issubclass(RiskError, NexusError))

    def test_risk_error_raises(self):
        """Test that RiskError can be raised."""
        with self.assertRaises(RiskError):
            raise RiskError("Risk limit violated")


class TestExecutionError(unittest.TestCase):
    """Test the ExecutionError exception."""

    def test_execution_error_inheritance(self):
        """Test that ExecutionError inherits from NexusError."""
        self.assertTrue(issubclass(ExecutionError, NexusError))

    def test_execution_error_raises(self):
        """Test that ExecutionError can be raised."""
        with self.assertRaises(ExecutionError):
            raise ExecutionError("Trade execution failed")


class TestValidationError(unittest.TestCase):
    """Test the ValidationError exception."""

    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from NexusError."""
        self.assertTrue(issubclass(ValidationError, NexusError))

    def test_validation_error_raises(self):
        """Test that ValidationError can be raised."""
        with self.assertRaises(ValidationError):
            raise ValidationError("Input validation failed")
