"""Tests for custom exceptions in nexus.core.exceptions."""

import pytest

from nexus.core.exceptions import (
    ConfigurationError,
    DataError,
    ExecutionError,
    NexusError,
    RiskError,
    StrategyError,
    ValidationError,
)


class TestNexusError:
    """Test the base NexusError exception."""

    def test_nexus_error_inheritance(self):
        """Test that NexusError inherits from Exception."""
        assert issubclass(NexusError, Exception)

    def test_nexus_error_raises(self):
        """Test that NexusError can be raised."""
        with pytest.raises(NexusError):
            raise NexusError("Test error")


class TestDataError:
    """Test the DataError exception."""

    def test_data_error_inheritance(self):
        """Test that DataError inherits from NexusError."""
        assert issubclass(DataError, NexusError)

    def test_data_error_raises(self):
        """Test that DataError can be raised."""
        with pytest.raises(DataError):
            raise DataError("Data fetch failed")


class TestConfigurationError:
    """Test the ConfigurationError exception."""

    def test_configuration_error_inheritance(self):
        """Test that ConfigurationError inherits from NexusError."""
        assert issubclass(ConfigurationError, NexusError)

    def test_configuration_error_raises(self):
        """Test that ConfigurationError can be raised."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Config validation failed")


class TestStrategyError:
    """Test the StrategyError exception."""

    def test_strategy_error_inheritance(self):
        """Test that StrategyError inherits from NexusError."""
        assert issubclass(StrategyError, NexusError)

    def test_strategy_error_raises(self):
        """Test that StrategyError can be raised."""
        with pytest.raises(StrategyError):
            raise StrategyError("Strategy execution failed")


class TestRiskError:
    """Test the RiskError exception."""

    def test_risk_error_inheritance(self):
        """Test that RiskError inherits from NexusError."""
        assert issubclass(RiskError, NexusError)

    def test_risk_error_raises(self):
        """Test that RiskError can be raised."""
        with pytest.raises(RiskError):
            raise RiskError("Risk limit violated")


class TestExecutionError:
    """Test the ExecutionError exception."""

    def test_execution_error_inheritance(self):
        """Test that ExecutionError inherits from NexusError."""
        assert issubclass(ExecutionError, NexusError)

    def test_execution_error_raises(self):
        """Test that ExecutionError can be raised."""
        with pytest.raises(ExecutionError):
            raise ExecutionError("Trade execution failed")


class TestValidationError:
    """Test the ValidationError exception."""

    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from NexusError."""
        assert issubclass(ValidationError, NexusError)

    def test_validation_error_raises(self):
        """Test that ValidationError can be raised."""
        with pytest.raises(ValidationError):
            raise ValidationError("Input validation failed")
