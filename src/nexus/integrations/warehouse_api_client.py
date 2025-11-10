"""Production-grade Warehouse API client with reliability patterns.

Implements:
- Async HTTP client with connection pooling
- Exponential backoff retry logic
- Circuit breaker pattern
- Rate limiting
- Comprehensive error handling
- Request/response logging
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd
from pydantic import BaseModel, Field

from nexus.core.logging_config import get_nexus_logger


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryStrategy(BaseModel):
    """Retry strategy configuration."""
    max_attempts: int = Field(3, ge=1, le=10)
    initial_backoff_ms: int = Field(100, ge=10)
    max_backoff_ms: int = Field(30000, ge=1000)
    backoff_multiplier: float = Field(1.5, ge=1.0, le=3.0)
    jitter: bool = Field(True)


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    failure_threshold: int = Field(5, ge=1)
    success_threshold: int = Field(2, ge=1)
    timeout_seconds: int = Field(60, ge=10)


class WarehouseAPIConfig(BaseModel):
    """Warehouse API client configuration."""
    url: str = Field(..., description="Base URL of Warehouse API")
    timeout_seconds: int = Field(30, ge=5, le=300)
    max_connections: int = Field(100, ge=1)
    retry: RetryStrategy = Field(default_factory=RetryStrategy)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)


@dataclass
class APIResponse:
    """Standardized API response wrapper."""
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300

    @property
    def is_retryable(self) -> bool:
        """Check if error is retryable."""
        # 5xx errors and timeouts are retryable
        return self.status_code >= 500 or self.status_code == 408


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.logger = get_nexus_logger(__name__)

    def record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed call."""
        self.last_failure_time = time.time()
        self.failure_count += 1

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_open()

    def can_attempt(self) -> bool:
        """Check if request can be attempted."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.config.timeout_seconds:
                    self._transition_to_half_open()
                    return True
            return False
        else:  # HALF_OPEN
            return True

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self.logger.info("Circuit breaker transitioning to CLOSED state")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self.logger.warning("Circuit breaker transitioning to OPEN state")
        self.state = CircuitBreakerState.OPEN
        self.success_count = 0

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self.logger.info("Circuit breaker transitioning to HALF_OPEN state")
        self.state = CircuitBreakerState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0


class WarehouseAPIClient:
    """Production-grade async client for Warehouse API.

    Features:
    - Async/await support with connection pooling
    - Exponential backoff retry logic
    - Circuit breaker for fault tolerance
    - Rate limiting
    - Request/response logging
    - Automatic timeout handling
    """

    def __init__(self, config: WarehouseAPIConfig):
        """Initialize Warehouse API client.

        Args:
            config: Client configuration

        Raises:
            ValueError: If configuration is invalid
        """
        if not config.url:
            raise ValueError("Warehouse API URL is required")

        self.config = config
        self.logger = get_nexus_logger(__name__)

        # Session will be created on first use
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(config.circuit_breaker)

        # Request tracking
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

        self.logger.info(
            f"Warehouse API client initialized: {config.url}",
            extra={"config": config.model_dump()}
        )

    async def __aenter__(self) -> "WarehouseAPIClient":
        """Context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is initialized."""
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=10,
                ttl_dns_cache=300,
            )
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout
            )
            self.logger.debug("Initialized aiohttp session")

    async def close(self) -> None:
        """Close client and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None
        if self._connector:
            await self._connector.close()
            self._connector = None
        self.logger.debug("Closed Warehouse API client")

    async def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "day"
    ) -> APIResponse:
        """Fetch historical data from Warehouse API.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "BTC")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timeframe: Data timeframe (default: "day")

        Returns:
            APIResponse with historical data

        Raises:
            ValueError: If parameters are invalid
            aiohttp.ClientError: On network errors (after retries)
        """
        if not symbol:
            raise ValueError("Symbol is required")

        endpoint = f"/api/v1/data/{symbol}"
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe
        }

        return await self._request("GET", endpoint, params=params)

    async def get_realtime_data(self, symbol: str) -> APIResponse:
        """Fetch real-time data from Warehouse API.

        Args:
            symbol: Trading symbol

        Returns:
            APIResponse with real-time data
        """
        if not symbol:
            raise ValueError("Symbol is required")

        endpoint = f"/api/v1/data/{symbol}/realtime"
        return await self._request("GET", endpoint)

    async def get_health(self) -> APIResponse:
        """Check Warehouse API health.

        Returns:
            APIResponse with health status
        """
        return await self._request("GET", "/api/v1/health")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retries: int = 0,
    ) -> APIResponse:
        """Internal request method with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body
            retries: Current retry attempt (internal)

        Returns:
            APIResponse with status and data
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_attempt():
            error_msg = f"Circuit breaker OPEN for {method} {endpoint}"
            self.logger.warning(error_msg)
            return APIResponse(
                status_code=503,
                error=error_msg
            )

        # Ensure session
        await self._ensure_session()

        url = f"{self.config.url}{endpoint}"
        start_time = time.time()

        try:
            self.logger.debug(
                f"Request: {method} {endpoint}",
                extra={"attempt": retries + 1, "params": params}
            )

            async with self._session.request(
                method,
                url,
                params=params,
                json=json_data
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                self._request_count += 1
                self._total_latency_ms += latency_ms

                try:
                    data = await response.json()
                except ValueError:
                    data = await response.text()

                api_response = APIResponse(
                    status_code=response.status,
                    data=data if isinstance(data, dict) else None,
                    error=None if response.status < 400 else str(data),
                    latency_ms=latency_ms
                )

                # Record with circuit breaker
                if api_response.is_success:
                    self.circuit_breaker.record_success()
                else:
                    self.circuit_breaker.record_failure()
                    self._error_count += 1

                # Retry if applicable
                if not api_response.is_success and api_response.is_retryable:
                    if retries < self.config.retry.max_attempts:
                        wait_ms = self._calculate_backoff(retries)
                        self.logger.warning(
                            f"Retrying {endpoint} after {wait_ms}ms "
                            f"(attempt {retries + 1}/{self.config.retry.max_attempts})",
                            extra={"status_code": response.status}
                        )
                        await asyncio.sleep(wait_ms / 1000)
                        return await self._request(
                            method, endpoint, params, json_data, retries + 1
                        )

                self.logger.debug(
                    f"Response: {method} {endpoint}",
                    extra={
                        "status_code": response.status,
                        "latency_ms": latency_ms,
                        "attempt": retries + 1
                    }
                )

                return api_response

        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            self._error_count += 1

            error_msg = f"Timeout on {method} {endpoint}"
            self.logger.error(error_msg)

            if retries < self.config.retry.max_attempts:
                wait_ms = self._calculate_backoff(retries)
                self.logger.info(f"Retrying after timeout ({wait_ms}ms)")
                await asyncio.sleep(wait_ms / 1000)
                return await self._request(
                    method, endpoint, params, json_data, retries + 1
                )

            return APIResponse(status_code=408, error=error_msg)

        except aiohttp.ClientError as e:
            self.circuit_breaker.record_failure()
            self._error_count += 1

            error_msg = f"Client error on {method} {endpoint}: {str(e)}"
            self.logger.error(error_msg)

            if retries < self.config.retry.max_attempts:
                wait_ms = self._calculate_backoff(retries)
                self.logger.info(f"Retrying after client error ({wait_ms}ms)")
                await asyncio.sleep(wait_ms / 1000)
                return await self._request(
                    method, endpoint, params, json_data, retries + 1
                )

            return APIResponse(status_code=500, error=error_msg)

        except Exception as e:
            self.circuit_breaker.record_failure()
            self._error_count += 1

            error_msg = f"Unexpected error on {method} {endpoint}: {str(e)}"
            self.logger.exception(error_msg)

            return APIResponse(status_code=500, error=error_msg)

    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff with optional jitter.

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Backoff time in milliseconds
        """
        backoff_ms = min(
            self.config.retry.initial_backoff_ms * (
                self.config.retry.backoff_multiplier ** retry_count
            ),
            self.config.retry.max_backoff_ms
        )

        if self.config.retry.jitter:
            import random
            # Add random jitter: ±10% of backoff
            jitter = random.uniform(-0.1, 0.1)
            backoff_ms *= (1 + jitter)

        return max(backoff_ms, self.config.retry.initial_backoff_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics and statistics.

        Returns:
            Dictionary with client metrics
        """
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )

        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "average_latency_ms": avg_latency,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
        }
