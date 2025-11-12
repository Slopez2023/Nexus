#!/usr/bin/env python3
"""
Warehouse API Test Suite

Tests all available endpoints of the Market Data Warehouse API
- Health & status checks
- Symbol listing
- Historical data retrieval
- Metrics monitoring
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nexus.integrations.warehouse_api_client import (
    WarehouseAPIClient,
    WarehouseAPIConfig,
)
from nexus.core.logging_config import get_nexus_logger


logger = get_nexus_logger(__name__)


class WarehouseAPITester:
    """Test suite for Warehouse API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.config = WarehouseAPIConfig(
            url=base_url,
            timeout_seconds=30,
            max_connections=100,
        )
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "tests": {},
            "summary": {},
        }

    async def run_all_tests(self) -> None:
        """Run all API tests."""
        async with WarehouseAPIClient(self.config) as client:
            print("\n" + "=" * 70)
            print("WAREHOUSE API TEST SUITE")
            print("=" * 70 + "\n")

            # Test 1: Health check
            await self._test_health(client)

            # Test 2: Status check
            await self._test_status(client)

            # Test 3: Available symbols
            await self._test_symbols(client)

            # Test 4: Historical data for multiple symbols
            await self._test_historical_data(client)

            # Test 5: Metrics
            await self._test_metrics(client)

            # Print summary
            self._print_summary(client)

    async def _test_health(self, client: WarehouseAPIClient) -> None:
        """Test health endpoint."""
        print("TEST 1: Root Health Check")
        print("-" * 70)

        try:
            # Try root endpoint first
            response = await client._request("GET", "/")

            self.results["tests"]["health"] = {
                "status": response.status_code,
                "success": response.is_success,
                "latency_ms": response.latency_ms,
                "data": response.data,
                "error": response.error,
            }

            if response.is_success:
                print(f"✓ Health check passed")
                print(f"  Status: {response.status_code}")
                print(f"  Latency: {response.latency_ms:.2f}ms")
                if response.data:
                    print(f"  Response: {json.dumps(response.data, indent=2)}")
            else:
                print(f"✗ Health check failed")
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.error}")

        except Exception as e:
            print(f"✗ Exception during health check: {e}")
            self.results["tests"]["health"] = {"error": str(e), "success": False}

        print()

    async def _test_status(self, client: WarehouseAPIClient) -> None:
        """Test status endpoint."""
        print("TEST 2: System Status")
        print("-" * 70)

        try:
            # Make direct request to status endpoint
            response = await client._request("GET", "/api/v1/status")

            self.results["tests"]["status"] = {
                "status": response.status_code,
                "success": response.is_success,
                "latency_ms": response.latency_ms,
                "data": response.data,
                "error": response.error,
            }

            if response.is_success:
                print(f"✓ Status check passed")
                print(f"  Status: {response.status_code}")
                print(f"  Latency: {response.latency_ms:.2f}ms")
                if response.data:
                    print(f"  Response: {json.dumps(response.data, indent=2)}")
            else:
                print(f"✗ Status check failed")
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.error}")

        except Exception as e:
            print(f"✗ Exception during status check: {e}")
            self.results["tests"]["status"] = {"error": str(e), "success": False}

        print()

    async def _test_symbols(self, client: WarehouseAPIClient) -> None:
        """Test available symbols endpoint."""
        print("TEST 3: Available Symbols")
        print("-" * 70)

        try:
            response = await client._request("GET", "/api/v1/symbols")

            self.results["tests"]["symbols"] = {
                "status": response.status_code,
                "success": response.is_success,
                "latency_ms": response.latency_ms,
                "data": response.data,
                "error": response.error,
            }

            if response.is_success:
                print(f"✓ Symbols endpoint passed")
                print(f"  Status: {response.status_code}")
                print(f"  Latency: {response.latency_ms:.2f}ms")
                if response.data:
                    if isinstance(response.data, dict) and "symbols" in response.data:
                        symbols = response.data["symbols"]
                        print(f"  Available symbols ({len(symbols)}): {', '.join(symbols[:10])}")
                        if len(symbols) > 10:
                            print(f"  ... and {len(symbols) - 10} more")
                    else:
                        print(f"  Response: {json.dumps(response.data, indent=2)}")
            else:
                print(f"✗ Symbols endpoint failed")
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.error}")

        except Exception as e:
            print(f"✗ Exception retrieving symbols: {e}")
            self.results["tests"]["symbols"] = {"error": str(e), "success": False}

        print()

    async def _test_historical_data(self, client: WarehouseAPIClient) -> None:
        """Test historical data endpoint for multiple symbols."""
        print("TEST 4: Historical Data")
        print("-" * 70)

        test_symbols = ["AAPL", "MSFT", "GOOGL", "BTC", "ETH"]
        start_date = "2024-01-01"
        end_date = "2024-12-31"

        historical_results = {}

        for symbol in test_symbols:
            try:
                # Use the correct endpoint format
                endpoint = f"/api/v1/historical/{symbol}"
                params = {
                    "start": start_date,
                    "end": end_date,
                }
                response = await client._request("GET", endpoint, params=params)

                historical_results[symbol] = {
                    "status": response.status_code,
                    "success": response.is_success,
                    "latency_ms": response.latency_ms,
                    "error": response.error,
                    "data_points": 0,
                }

                if response.is_success and response.data:
                    # Try to count data points
                    if isinstance(response.data, dict):
                        if "data" in response.data:
                            data_points = len(response.data["data"])
                            historical_results[symbol]["data_points"] = data_points
                            print(f"✓ {symbol}: {data_points} data points ({response.latency_ms:.2f}ms)")
                        else:
                            print(f"✓ {symbol}: Data received ({response.latency_ms:.2f}ms)")
                    elif isinstance(response.data, list):
                        data_points = len(response.data)
                        historical_results[symbol]["data_points"] = data_points
                        print(f"✓ {symbol}: {data_points} data points ({response.latency_ms:.2f}ms)")
                else:
                    print(f"✗ {symbol}: Failed (Status {response.status_code})")
                    if response.error:
                        print(f"  Error: {response.error}")

            except Exception as e:
                print(f"✗ {symbol}: Exception - {e}")
                historical_results[symbol] = {"error": str(e), "success": False}

        self.results["tests"]["historical_data"] = historical_results
        print()

    async def _test_metrics(self, client: WarehouseAPIClient) -> None:
        """Test metrics endpoint."""
        print("TEST 5: Metrics")
        print("-" * 70)

        try:
            response = await client._request("GET", "/api/v1/metrics")

            self.results["tests"]["metrics"] = {
                "status": response.status_code,
                "success": response.is_success,
                "latency_ms": response.latency_ms,
                "data": response.data,
                "error": response.error,
            }

            if response.is_success:
                print(f"✓ Metrics endpoint passed")
                print(f"  Status: {response.status_code}")
                print(f"  Latency: {response.latency_ms:.2f}ms")
                if response.data:
                    print(f"  Response: {json.dumps(response.data, indent=2)}")
            else:
                print(f"✗ Metrics endpoint failed")
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.error}")

        except Exception as e:
            print(f"✗ Exception retrieving metrics: {e}")
            self.results["tests"]["metrics"] = {"error": str(e), "success": False}

        print()

    def _print_summary(self, client: WarehouseAPIClient) -> None:
        """Print test summary."""
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70 + "\n")

        passed = 0
        failed = 0

        for test_name, test_result in self.results["tests"].items():
            if isinstance(test_result, dict):
                if test_name == "historical_data":
                    # Count successes in historical data
                    for symbol, result in test_result.items():
                        if result.get("success", False):
                            passed += 1
                        else:
                            failed += 1
                else:
                    if test_result.get("success", False):
                        passed += 1
                        status = "✓ PASS"
                    else:
                        failed += 1
                        status = "✗ FAIL"
                    print(f"{status}: {test_name}")

        print(f"\nClient Metrics:")
        metrics = client.get_metrics()
        print(f"  Total requests: {metrics['total_requests']}")
        print(f"  Total errors: {metrics['total_errors']}")
        print(f"  Error rate: {metrics['error_rate']:.2%}")
        print(f"  Avg latency: {metrics['average_latency_ms']:.2f}ms")
        print(f"  Circuit breaker state: {metrics['circuit_breaker_state']}")

        self.results["summary"] = {
            "tests_passed": passed,
            "tests_failed": failed,
            "total_tests": passed + failed,
            "client_metrics": metrics,
        }

        print(f"\nOverall: {passed} passed, {failed} failed")

        # Save results to file
        results_file = Path(__file__).parent / "warehouse_api_test_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nResults saved to: {results_file}")

        print("\n" + "=" * 70 + "\n")


async def main():
    """Main entry point."""
    tester = WarehouseAPITester(base_url="http://localhost:8000")
    try:
        await tester.run_all_tests()
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
