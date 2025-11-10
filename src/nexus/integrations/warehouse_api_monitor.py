"""Monitoring and health tracking for Warehouse API integration."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from nexus.core.logging_config import get_nexus_logger


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """Health metrics snapshot."""
    status: HealthStatus
    timestamp: datetime
    api_response_time_ms: Optional[float] = None
    error_rate: float = 0.0
    circuit_breaker_state: Optional[str] = None
    last_successful_request: Optional[datetime] = None
    consecutive_failures: int = 0
    message: str = ""


class WarehouseAPIMonitor:
    """Monitors Warehouse API health and performance."""

    def __init__(
        self,
        error_rate_threshold: float = 0.05,
        response_time_threshold_ms: float = 5000,
        consecutive_failure_threshold: int = 5
    ):
        """Initialize API monitor.

        Args:
            error_rate_threshold: Error rate threshold for degraded status
            response_time_threshold_ms: Response time threshold in milliseconds
            consecutive_failure_threshold: Max consecutive failures before unhealthy
        """
        self.error_rate_threshold = error_rate_threshold
        self.response_time_threshold_ms = response_time_threshold_ms
        self.consecutive_failure_threshold = consecutive_failure_threshold

        self.logger = get_nexus_logger(__name__)

        # Metrics tracking
        self._total_requests = 0
        self._total_errors = 0
        self._consecutive_failures = 0
        self._last_successful_request: Optional[datetime] = None
        self._response_times: List[float] = []
        self._max_response_times_history = 1000

        # Health history
        self._health_history: List[HealthMetrics] = []
        self._max_history = 100

    def record_request(
        self,
        success: bool,
        response_time_ms: float,
        error: Optional[str] = None
    ) -> None:
        """Record API request result.

        Args:
            success: Whether request was successful
            response_time_ms: Response time in milliseconds
            error: Error message if unsuccessful
        """
        self._total_requests += 1
        self._response_times.append(response_time_ms)

        # Keep response times history bounded
        if len(self._response_times) > self._max_response_times_history:
            self._response_times.pop(0)

        if success:
            self._consecutive_failures = 0
            self._last_successful_request = datetime.now()
        else:
            self._consecutive_failures += 1
            self._total_errors += 1

            if error:
                self.logger.warning(f"API request failed: {error}")

    def get_health(self) -> HealthMetrics:
        """Get current health status.

        Returns:
            HealthMetrics with current health status
        """
        # Calculate metrics
        error_rate = (
            self._total_errors / self._total_requests
            if self._total_requests > 0
            else 0.0
        )

        avg_response_time = (
            sum(self._response_times) / len(self._response_times)
            if self._response_times
            else None
        )

        # Determine health status
        if self._total_requests == 0:
            status = HealthStatus.UNKNOWN
            message = "No requests recorded yet"
        elif self._consecutive_failures >= self.consecutive_failure_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"{self._consecutive_failures} consecutive failures"
        elif error_rate > self.error_rate_threshold:
            status = HealthStatus.DEGRADED
            message = f"High error rate: {error_rate:.2%}"
        elif (avg_response_time and 
              avg_response_time > self.response_time_threshold_ms):
            status = HealthStatus.DEGRADED
            message = f"High response time: {avg_response_time:.0f}ms"
        else:
            status = HealthStatus.HEALTHY
            message = "All systems operational"

        metrics = HealthMetrics(
            status=status,
            timestamp=datetime.now(),
            api_response_time_ms=avg_response_time,
            error_rate=error_rate,
            last_successful_request=self._last_successful_request,
            consecutive_failures=self._consecutive_failures,
            message=message
        )

        # Record in history
        self._health_history.append(metrics)
        if len(self._health_history) > self._max_history:
            self._health_history.pop(0)

        return metrics

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary.

        Returns:
            Dictionary with all tracked metrics
        """
        health = self.get_health()

        response_times = self._response_times
        percentiles = {}
        if response_times:
            sorted_times = sorted(response_times)
            percentiles = {
                "p50": sorted_times[len(sorted_times) // 2],
                "p95": sorted_times[int(len(sorted_times) * 0.95)],
                "p99": sorted_times[int(len(sorted_times) * 0.99)],
                "min": min(response_times),
                "max": max(response_times),
            }

        return {
            "health_status": health.status.value,
            "health_message": health.message,
            "timestamp": health.timestamp.isoformat(),
            "metrics": {
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": health.error_rate,
                "consecutive_failures": self._consecutive_failures,
                "last_successful_request": (
                    self._last_successful_request.isoformat()
                    if self._last_successful_request else None
                ),
            },
            "response_time_ms": {
                "current": (
                    self._response_times[-1] if self._response_times else None
                ),
                "average": health.api_response_time_ms,
                **percentiles
            },
            "thresholds": {
                "error_rate": self.error_rate_threshold,
                "response_time_ms": self.response_time_threshold_ms,
                "consecutive_failures": self.consecutive_failure_threshold,
            }
        }

    def get_health_history(
        self,
        hours: int = 1
    ) -> List[HealthMetrics]:
        """Get health metrics history.

        Args:
            hours: Number of hours of history to return

        Returns:
            List of health metrics within specified timeframe
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self._health_history if m.timestamp >= cutoff_time]

    def reset_metrics(self) -> None:
        """Reset all metrics and history."""
        self._total_requests = 0
        self._total_errors = 0
        self._consecutive_failures = 0
        self._last_successful_request = None
        self._response_times.clear()
        self._health_history.clear()
        self.logger.info("Metrics reset")

    def is_healthy(self) -> bool:
        """Quick health check.

        Returns:
            True if system is healthy or degraded but operational
        """
        health = self.get_health()
        return health.status != HealthStatus.UNHEALTHY

    def should_fallback(self) -> bool:
        """Check if should fallback to legacy data sources.

        Returns:
            True if health is too poor to use Warehouse API
        """
        health = self.get_health()
        return health.status == HealthStatus.UNHEALTHY
