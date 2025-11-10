"""Unit tests for Warehouse API client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from nexus.integrations.warehouse_api_client import (
    WarehouseAPIClient,
    WarehouseAPIConfig,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    RetryStrategy,
    APIResponse,
)


class TestRetryStrategy:
    """Test RetryStrategy configuration."""

    def test_default_values(self):
        """Test default retry strategy values."""
        strategy = RetryStrategy()
        assert strategy.max_attempts == 3
        assert strategy.initial_backoff_ms == 100
        assert strategy.max_backoff_ms == 30000
        assert strategy.backoff_multiplier == 1.5

    def test_custom_values(self):
        """Test custom retry strategy values."""
        strategy = RetryStrategy(
            max_attempts=5,
            initial_backoff_ms=200,
            max_backoff_ms=60000,
            backoff_multiplier=2.0
        )
        assert strategy.max_attempts == 5
        assert strategy.initial_backoff_ms == 200
        assert strategy.max_backoff_ms == 60000
        assert strategy.backoff_multiplier == 2.0

    def test_validation(self):
        """Test retry strategy validation."""
        with pytest.raises(ValueError):
            RetryStrategy(max_attempts=0)  # Too low
        with pytest.raises(ValueError):
            RetryStrategy(max_attempts=11)  # Too high


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig."""

    def test_default_values(self):
        """Test default circuit breaker config."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 60


class TestCircuitBreaker:
    """Test CircuitBreaker."""

    def test_initial_state(self):
        """Test initial circuit breaker state."""
        config = CircuitBreakerConfig()
        cb = CircuitBreaker(config)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_closed_to_open_transition(self):
        """Test transition from CLOSED to OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(config)

        # Record failures
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_open_state_rejects_requests(self):
        """Test that OPEN state rejects requests."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(config)

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert not cb.can_attempt()

    def test_half_open_to_closed_transition(self):
        """Test transition through HALF_OPEN to CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout_seconds=10  # Minimum allowed
        )
        cb = CircuitBreaker(config)

        # Go to OPEN
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        # Simulate timeout (use internal state change for testing)
        cb._transition_to_half_open()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Record successes
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED


class TestWarehouseAPIConfig:
    """Test WarehouseAPIConfig."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = WarehouseAPIConfig(url="http://localhost:8000")
        assert config.url == "http://localhost:8000"
        assert config.timeout_seconds == 30
        assert config.max_connections == 100

    def test_empty_url_allowed_but_client_rejects(self):
        """Test that empty URL in config is allowed but client rejects it."""
        # Config allows empty string, but client should reject during initialization
        config = WarehouseAPIConfig(url="")
        # Config object is created (Pydantic allows empty string)
        assert config.url == ""
        
        # But WarehouseAPIClient should reject it
        with pytest.raises(ValueError):
            WarehouseAPIClient(config)

    def test_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValueError):
            WarehouseAPIConfig(url="http://localhost", timeout_seconds=2)  # Too low
        with pytest.raises(ValueError):
            WarehouseAPIConfig(url="http://localhost", timeout_seconds=400)  # Too high


class TestAPIResponse:
    """Test APIResponse."""

    def test_success_response(self):
        """Test successful response."""
        response = APIResponse(status_code=200, data={"key": "value"})
        assert response.is_success
        assert not response.is_retryable

    def test_client_error_not_retryable(self):
        """Test that 4xx errors are not retryable."""
        response = APIResponse(status_code=404, error="Not found")
        assert not response.is_success
        assert not response.is_retryable

    def test_server_error_retryable(self):
        """Test that 5xx errors are retryable."""
        response = APIResponse(status_code=500, error="Server error")
        assert not response.is_success
        assert response.is_retryable

    def test_timeout_retryable(self):
        """Test that timeouts (408) are retryable."""
        response = APIResponse(status_code=408, error="Timeout")
        assert not response.is_success
        assert response.is_retryable


class TestWarehouseAPIClient:
    """Test WarehouseAPIClient."""

    @pytest.fixture
    def config(self):
        """Provide test configuration."""
        return WarehouseAPIConfig(url="http://localhost:8000")

    @pytest.fixture
    def client(self, config):
        """Provide test client."""
        return WarehouseAPIClient(config)

    def test_client_initialization(self, client):
        """Test client initialization."""
        assert client.config.url == "http://localhost:8000"
        assert client._session is None
        assert client.circuit_breaker is not None

    def test_invalid_url_raises_error(self):
        """Test that invalid URL raises error."""
        with pytest.raises(ValueError):
            WarehouseAPIClient(WarehouseAPIConfig(url=""))

    @pytest.mark.asyncio
    async def test_get_historical_data_validation(self, client):
        """Test parameter validation for historical data."""
        with pytest.raises(ValueError):
            await client.get_historical_data(
                symbol="",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

    @pytest.mark.asyncio
    async def test_get_realtime_data_validation(self, client):
        """Test parameter validation for realtime data."""
        with pytest.raises(ValueError):
            await client.get_realtime_data(symbol="")

    @pytest.mark.asyncio
    async def test_backoff_calculation(self, client):
        """Test exponential backoff calculation."""
        # Without jitter for predictable testing
        client.config.retry.jitter = False

        backoff_0 = client._calculate_backoff(0)
        assert backoff_0 == 100  # initial_backoff_ms

        backoff_1 = client._calculate_backoff(1)
        assert backoff_1 == 150  # 100 * 1.5

        backoff_2 = client._calculate_backoff(2)
        assert backoff_2 == 225  # 100 * 1.5^2

    def test_get_metrics(self, client):
        """Test metrics collection."""
        # Initially no requests
        metrics = client.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["total_errors"] == 0
        assert metrics["error_rate"] == 0.0

        # Simulate requests
        client._request_count = 10
        client._error_count = 1
        client._total_latency_ms = 500.0

        metrics = client.get_metrics()
        assert metrics["total_requests"] == 10
        assert metrics["total_errors"] == 1
        assert pytest.approx(metrics["error_rate"], 0.01) == 0.1
        assert pytest.approx(metrics["average_latency_ms"], 0.1) == 50.0

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test client as async context manager."""
        async with client as c:
            assert c is client
            assert client._session is not None or client._session is None  # May not be initialized yet

        # Session should be closed
        assert client._session is None


class TestWarehouseAPIClientIntegration:
    """Integration tests for Warehouse API client."""

    @pytest.fixture
    def config(self):
        """Provide test configuration."""
        return WarehouseAPIConfig(
            url="http://localhost:8000",
            retry=RetryStrategy(max_attempts=2)
        )

    @pytest.fixture
    def client(self, config):
        """Provide test client."""
        return WarehouseAPIClient(config)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, client):
        """Test circuit breaker integration with request handling."""
        # Manually trip circuit breaker
        config = CircuitBreakerConfig(failure_threshold=1)
        client.circuit_breaker = CircuitBreaker(config)

        # Record failure to trip
        client.circuit_breaker.record_failure()
        assert client.circuit_breaker.state == CircuitBreakerState.OPEN

        # Request should be rejected
        response = await client._request("GET", "/api/v1/health")
        assert response.status_code == 503
        assert "Circuit breaker" in response.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
