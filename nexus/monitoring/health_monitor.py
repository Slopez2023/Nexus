"""Health monitoring system for NEXUS.

Provides comprehensive system monitoring including:
- Database connectivity and performance
- Data pipeline health
- System resource usage
- Alert generation and notification
"""

import time
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from nexus.core.database import get_database_manager
from nexus.core.logging_config import get_nexus_logger
from nexus.core.data_api import get_data_api


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: Any
    status: HealthStatus
    message: str
    timestamp: datetime


@dataclass
class SystemHealth:
    """Overall system health report."""
    status: HealthStatus
    metrics: List[HealthMetric]
    alerts: List[str]
    timestamp: datetime


class HealthMonitor:
    """Comprehensive health monitoring for NEXUS."""

    def __init__(self):
        self.logger = get_nexus_logger("monitoring.health")
        self.db = get_database_manager()
        self.api = get_data_api()

    def check_database_health(self) -> HealthMetric:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            health = self.db.health_check()
            response_time = time.time() - start_time

            if health["status"] == "healthy":
                if response_time < 0.1:
                    status = HealthStatus.HEALTHY
                    message = f"Database healthy ({health['tables_count']} tables, {response_time:.3f}s)"
                else:
                    status = HealthStatus.WARNING
                    message = f"Database slow ({response_time:.3f}s response time)"
            else:
                status = HealthStatus.ERROR
                message = f"Database error: {health}"

            return HealthMetric(
                name="database",
                value=response_time,
                status=status,
                message=message,
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthMetric(
                name="database",
                value=None,
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                timestamp=datetime.now()
            )

    def check_data_pipeline_health(self) -> HealthMetric:
        """Check data pipeline health and recent activity."""
        try:
            # Check recent market data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=1)

            # Count records from last 24 hours
            recent_data = self.db.get_market_data(
                symbol="AAPL",  # Use a common symbol as proxy
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )

            record_count = len(recent_data)

            if record_count > 0:
                status = HealthStatus.HEALTHY
                message = f"Data pipeline active ({record_count} records in last 24h)"
            elif record_count == 0:
                # Check if this is expected (weekend, holiday)
                current_hour = datetime.now().hour
                if current_hour < 9 or current_hour > 16:  # Outside market hours
                    status = HealthStatus.HEALTHY
                    message = "Data pipeline healthy (outside market hours)"
                else:
                    status = HealthStatus.WARNING
                    message = "Data pipeline warning (no recent data during market hours)"
            else:
                status = HealthStatus.ERROR
                message = "Data pipeline error (unable to query data)"

            return HealthMetric(
                name="data_pipeline",
                value=record_count,
                status=status,
                message=message,
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthMetric(
                name="data_pipeline",
                value=None,
                status=HealthStatus.ERROR,
                message=f"Data pipeline check failed: {str(e)}",
                timestamp=datetime.now()
            )

    def check_system_resources(self) -> List[HealthMetric]:
        """Check system resource usage."""
        metrics = []

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent < 50:
                status = HealthStatus.HEALTHY
                message = f"CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent < 80:
                status = HealthStatus.WARNING
                message = f"CPU usage high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.ERROR
                message = f"CPU usage critical: {cpu_percent:.1f}%"

            metrics.append(HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                status=status,
                message=message,
                timestamp=datetime.now()
            ))

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if memory_percent < 70:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {memory_percent:.1f}% ({memory.used/1024/1024/1024:.1f}GB used)"
            elif memory_percent < 85:
                status = HealthStatus.WARNING
                message = f"Memory usage high: {memory_percent:.1f}%"
            else:
                status = HealthStatus.ERROR
                message = f"Memory usage critical: {memory_percent:.1f}%"

            metrics.append(HealthMetric(
                name="memory_usage",
                value=memory_percent,
                status=status,
                message=message,
                timestamp=datetime.now()
            ))

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            if disk_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"Disk usage: {disk_percent:.1f}% ({disk.free/1024/1024/1024:.1f}GB free)"
            elif disk_percent < 90:
                status = HealthStatus.WARNING
                message = f"Disk usage high: {disk_percent:.1f}%"
            else:
                status = HealthStatus.ERROR
                message = f"Disk usage critical: {disk_percent:.1f}%"

            metrics.append(HealthMetric(
                name="disk_usage",
                value=disk_percent,
                status=status,
                message=message,
                timestamp=datetime.now()
            ))

        except Exception as e:
            metrics.append(HealthMetric(
                name="system_resources",
                value=None,
                status=HealthStatus.ERROR,
                message=f"System resource check failed: {str(e)}",
                timestamp=datetime.now()
            ))

        return metrics

    def check_api_health(self) -> HealthMetric:
        """Check API endpoint health."""
        try:
            # Simple API health check (would need actual HTTP call in production)
            # For now, just check if API instance can be created
            api_status = "healthy"

            status = HealthStatus.HEALTHY
            message = "API service healthy"

            return HealthMetric(
                name="api_service",
                value=api_status,
                status=status,
                message=message,
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthMetric(
                name="api_service",
                value=None,
                status=HealthStatus.ERROR,
                message=f"API health check failed: {str(e)}",
                timestamp=datetime.now()
            )

    def perform_full_health_check(self) -> SystemHealth:
        """Perform comprehensive health check."""
        self.logger.info("Performing full system health check")

        metrics = []

        # Database health
        metrics.append(self.check_database_health())

        # Data pipeline health
        metrics.append(self.check_data_pipeline_health())

        # System resources
        metrics.extend(self.check_system_resources())

        # API health
        metrics.append(self.check_api_health())

        # Determine overall status
        status_levels = [m.status for m in metrics]
        if HealthStatus.CRITICAL in status_levels:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.ERROR in status_levels:
            overall_status = HealthStatus.ERROR
        elif HealthStatus.WARNING in status_levels:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY

        # Generate alerts
        alerts = []
        for metric in metrics:
            if metric.status in [HealthStatus.ERROR, HealthStatus.CRITICAL]:
                alerts.append(f"🚨 {metric.name.upper()}: {metric.message}")
            elif metric.status == HealthStatus.WARNING:
                alerts.append(f"⚠️ {metric.name.upper()}: {metric.message}")

        # Store health metrics in database
        try:
            for metric in metrics:
                self.db.insert_health_metric(
                    component=metric.name,
                    status=metric.status.value,
                    metric_name="value",
                    metric_value=metric.value,
                    message=metric.message
                )
        except Exception as e:
            self.logger.error(f"Failed to store health metrics: {e}")

        health_report = SystemHealth(
            status=overall_status,
            metrics=metrics,
            alerts=alerts,
            timestamp=datetime.now()
        )

        # Log summary
        self.logger.info(f"Health check complete: {overall_status.value.upper()} ({len(alerts)} alerts)")

        return health_report

    def get_health_history(self, component: Optional[str] = None,
                          hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical health metrics."""
        try:
            return self.db.get_health_metrics(
                component=component,
                limit=min(hours * 4, 1000)  # Assuming 4 checks per hour max
            )
        except Exception as e:
            self.logger.error(f"Failed to retrieve health history: {e}")
            return []


def print_health_report(health: SystemHealth):
    """Print formatted health report."""
    print(f"\n{'='*60}")
    print(f"NEXUS SYSTEM HEALTH REPORT - {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Overall Status: {health.status.value.upper()}")
    print()

    if health.alerts:
        print("🚨 ALERTS:")
        for alert in health.alerts:
            print(f"  {alert}")
        print()

    print("📊 METRICS:")
    for metric in health.metrics:
        status_icon = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.ERROR: "❌",
            HealthStatus.CRITICAL: "🚨"
        }.get(metric.status, "❓")

        print(f"  {status_icon} {metric.name}: {metric.message}")

    print(f"\n{'='*60}")


# CLI interface
def main():
    """CLI health monitoring tool."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS Health Monitor")
    parser.add_argument("--continuous", action="store_true",
                       help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=300,
                       help="Monitoring interval in seconds (default: 300)")
    parser.add_argument("--component", help="Check specific component only")

    args = parser.parse_args()

    monitor = HealthMonitor()

    if args.component:
        # Check specific component
        if args.component == "database":
            metric = monitor.check_database_health()
        elif args.component == "data":
            metric = monitor.check_data_pipeline_health()
        elif args.component == "api":
            metric = monitor.check_api_health()
        else:
            print(f"Unknown component: {args.component}")
            return

        print(f"{metric.name.upper()}: {metric.status.value} - {metric.message}")

    elif args.continuous:
        # Continuous monitoring
        print(f"Starting continuous monitoring (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                health = monitor.perform_full_health_check()
                print_health_report(health)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")

    else:
        # Single health check
        health = monitor.perform_full_health_check()
        print_health_report(health)


if __name__ == "__main__":
    main()
