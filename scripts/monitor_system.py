#!/usr/bin/env python3
"""Simple CLI monitoring script for NEXUS system health.

Provides quick health checks and alerts without full GUI.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nexus.monitoring.health_monitor import HealthMonitor, print_health_report
from nexus.core.logging_config import get_nexus_logger


def main():
    """CLI system monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS System Monitor")
    parser.add_argument("--continuous", action="store_true",
                       help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=300,
                       help="Monitoring interval in seconds (default: 300)")
    parser.add_argument("--quiet", action="store_true",
                       help="Only show alerts and errors")

    args = parser.parse_args()

    logger = get_nexus_logger("monitor.cli")
    monitor = HealthMonitor()

    if args.continuous:
        logger.info(f"Starting continuous monitoring (interval: {args.interval}s)")
        print(f"🖥️ NEXUS System Monitor - Continuous Mode")
        print(f"Interval: {args.interval} seconds")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                health = monitor.perform_full_health_check()

                if not args.quiet:
                    print_health_report(health)
                elif health.alerts:
                    # Only show alerts in quiet mode
                    print(f"\n🚨 ALERTS DETECTED - {health.timestamp.strftime('%H:%M:%S')}")
                    for alert in health.alerts:
                        print(f"  {alert}")
                    print()

                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            logger.info("Continuous monitoring stopped by user")

    else:
        # Single check
        logger.info("Performing single health check")
        health = monitor.perform_full_health_check()
        print_health_report(health)

        # Exit with error code if system unhealthy
        if health.status.value in ["error", "critical"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
