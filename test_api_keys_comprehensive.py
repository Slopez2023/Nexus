#!/usr/bin/env python3
"""Comprehensive test of all API keys and endpoints."""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class APITester:
    """Comprehensive API testing suite."""

    def __init__(self):
        self.results: List[Dict] = []
        self.api_keys = {
            "MASSIVE_API_KEY": os.getenv("MASSIVE_API_KEY"),
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
            "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
            "COINGECKO_API_KEY": os.getenv("COINGECKO_API_KEY"),
        }

    def test_env_keys(self) -> None:
        """Test that API keys are loaded from environment."""
        print("\n" + "=" * 70)
        print("TESTING ENVIRONMENT VARIABLES")
        print("=" * 70)

        for key_name, key_value in self.api_keys.items():
            status = "✓" if key_value else "✗"
            value_preview = (
                f"{key_value[:10]}...{key_value[-4:]}" if key_value else "NOT SET"
            )
            print(f"{status} {key_name:20} -> {value_preview}")
            self.results.append(
                {
                    "test": f"Env Var: {key_name}",
                    "status": "pass" if key_value else "fail",
                    "details": "Key loaded" if key_value else "Key not found",
                }
            )

    def test_polygon_api(self) -> None:
        """Test Polygon API (MASSIVE_API_KEY)."""
        print("\n" + "=" * 70)
        print("TESTING POLYGON API")
        print("=" * 70)

        api_key = self.api_keys["MASSIVE_API_KEY"]
        if not api_key:
            print("✗ Polygon API key not set")
            self.results.append(
                {"test": "Polygon API", "status": "skip", "details": "No API key"}
            )
            return

        try:
            # Test basic market status endpoint
            url = "https://api.polygon.io/v1/marketstatus?apikey=" + api_key
            print(f"Testing: GET {url[:80]}...")

            response = requests.get(url, timeout=10)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✓ Polygon API working")
                print(f"  Market status: {data.get('status', 'unknown')}")
                self.results.append(
                    {
                        "test": "Polygon API",
                        "status": "pass",
                        "details": f"Status code: {response.status_code}",
                    }
                )
            elif response.status_code == 401:
                print(f"✗ Polygon API: Unauthorized (invalid key)")
                self.results.append(
                    {
                        "test": "Polygon API",
                        "status": "fail",
                        "details": "Unauthorized - invalid API key",
                    }
                )
            else:
                print(f"✗ Polygon API: {response.status_code}")
                self.results.append(
                    {
                        "test": "Polygon API",
                        "status": "fail",
                        "details": f"Status code: {response.status_code}",
                    }
                )
        except Exception as e:
            print(f"✗ Polygon API error: {str(e)}")
            self.results.append(
                {"test": "Polygon API", "status": "error", "details": str(e)}
            )

    def test_openrouter_api(self) -> None:
        """Test OpenRouter API."""
        print("\n" + "=" * 70)
        print("TESTING OPENROUTER API")
        print("=" * 70)

        api_key = self.api_keys["OPENROUTER_API_KEY"]
        if not api_key:
            print("✗ OpenRouter API key not set")
            self.results.append(
                {"test": "OpenRouter API", "status": "skip", "details": "No API key"}
            )
            return

        try:
            # Test OpenRouter API with a simple request
            url = "https://openrouter.ai/api/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}

            print(f"Testing: GET {url}")

            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                print(f"✓ OpenRouter API working")
                print(f"  Available models: {len(models)}")
                self.results.append(
                    {
                        "test": "OpenRouter API",
                        "status": "pass",
                        "details": f"Status code: {response.status_code}, Models: {len(models)}",
                    }
                )
            elif response.status_code == 401:
                print(f"✗ OpenRouter API: Unauthorized (invalid key)")
                self.results.append(
                    {
                        "test": "OpenRouter API",
                        "status": "fail",
                        "details": "Unauthorized - invalid API key",
                    }
                )
            else:
                print(f"✗ OpenRouter API: {response.status_code}")
                self.results.append(
                    {
                        "test": "OpenRouter API",
                        "status": "fail",
                        "details": f"Status code: {response.status_code}",
                    }
                )
        except Exception as e:
            print(f"✗ OpenRouter API error: {str(e)}")
            self.results.append(
                {"test": "OpenRouter API", "status": "error", "details": str(e)}
            )

    def test_deepseek_api(self) -> None:
        """Test DeepSeek API."""
        print("\n" + "=" * 70)
        print("TESTING DEEPSEEK API")
        print("=" * 70)

        api_key = self.api_keys["DEEPSEEK_API_KEY"]
        if not api_key:
            print("✗ DeepSeek API key not set")
            self.results.append(
                {"test": "DeepSeek API", "status": "skip", "details": "No API key"}
            )
            return

        try:
            # Test DeepSeek API with a simple request
            url = "https://api.deepseek.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}

            print(f"Testing: GET {url}")

            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✓ DeepSeek API working")
                self.results.append(
                    {
                        "test": "DeepSeek API",
                        "status": "pass",
                        "details": f"Status code: {response.status_code}",
                    }
                )
            elif response.status_code == 401:
                print(f"✗ DeepSeek API: Unauthorized (invalid key)")
                self.results.append(
                    {
                        "test": "DeepSeek API",
                        "status": "fail",
                        "details": "Unauthorized - invalid API key",
                    }
                )
            else:
                print(f"✗ DeepSeek API: {response.status_code}")
                self.results.append(
                    {
                        "test": "DeepSeek API",
                        "status": "fail",
                        "details": f"Status code: {response.status_code}",
                    }
                )
        except Exception as e:
            print(f"✗ DeepSeek API error: {str(e)}")
            self.results.append(
                {"test": "DeepSeek API", "status": "error", "details": str(e)}
            )

    def test_coingecko_api(self) -> None:
        """Test CoinGecko API."""
        print("\n" + "=" * 70)
        print("TESTING COINGECKO API")
        print("=" * 70)

        api_key = self.api_keys["COINGECKO_API_KEY"]
        if not api_key:
            print("✗ CoinGecko API key not set")
            self.results.append(
                {"test": "CoinGecko API", "status": "skip", "details": "No API key"}
            )
            return

        try:
            # Test CoinGecko API
            url = "https://pro-api.coingecko.com/api/v3/ping"
            params = {"x_cg_pro_api_key": api_key}

            print(f"Testing: GET {url}")

            response = requests.get(url, params=params, timeout=10)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                print(f"✓ CoinGecko API working")
                self.results.append(
                    {
                        "test": "CoinGecko API",
                        "status": "pass",
                        "details": f"Status code: {response.status_code}",
                    }
                )
            elif response.status_code == 401:
                print(f"✗ CoinGecko API: Unauthorized (invalid key)")
                self.results.append(
                    {
                        "test": "CoinGecko API",
                        "status": "fail",
                        "details": "Unauthorized - invalid API key",
                    }
                )
            else:
                print(f"✗ CoinGecko API: {response.status_code}")
                self.results.append(
                    {
                        "test": "CoinGecko API",
                        "status": "fail",
                        "details": f"Status code: {response.status_code}",
                    }
                )
        except Exception as e:
            print(f"✗ CoinGecko API error: {str(e)}")
            self.results.append(
                {"test": "CoinGecko API", "status": "error", "details": str(e)}
            )

    def test_nexus_data_api(self) -> None:
        """Test local NEXUS Data API endpoints."""
        print("\n" + "=" * 70)
        print("TESTING NEXUS DATA API (local)")
        print("=" * 70)

        base_url = "http://localhost:8000"
        endpoints = [
            ("Health Check", "GET", "/api/v1/health", None),
            ("Data Sources", "GET", "/api/v1/sources", None),
        ]

        print(f"Connecting to: {base_url}")

        for name, method, path, params in endpoints:
            try:
                url = f"{base_url}{path}"
                print(f"Testing: {method} {path}")

                response = requests.get(url, timeout=5)
                status_ok = response.status_code < 400

                if status_ok:
                    print(f"✓ {name}: {response.status_code}")
                    self.results.append(
                        {
                            "test": f"NEXUS API: {name}",
                            "status": "pass",
                            "details": f"Status code: {response.status_code}",
                        }
                    )
                else:
                    print(f"✗ {name}: {response.status_code}")
                    self.results.append(
                        {
                            "test": f"NEXUS API: {name}",
                            "status": "fail",
                            "details": f"Status code: {response.status_code}",
                        }
                    )
            except requests.exceptions.ConnectionError:
                print(f"✗ {name}: Connection refused (server not running)")
                self.results.append(
                    {
                        "test": f"NEXUS API: {name}",
                        "status": "fail",
                        "details": "Connection refused - server not running",
                    }
                )
            except Exception as e:
                print(f"✗ {name}: {str(e)}")
                self.results.append(
                    {
                        "test": f"NEXUS API: {name}",
                        "status": "error",
                        "details": str(e),
                    }
                )

    def print_summary(self) -> None:
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")
        errors = sum(1 for r in self.results if r["status"] == "error")
        skipped = sum(1 for r in self.results if r["status"] == "skip")

        print(f"Passed:  {passed}")
        print(f"Failed:  {failed}")
        print(f"Errors:  {errors}")
        print(f"Skipped: {skipped}")
        print(f"Total:   {len(self.results)}")

        if failed > 0 or errors > 0:
            print("\n" + "=" * 70)
            print("FAILING TESTS:")
            print("=" * 70)
            for result in self.results:
                if result["status"] in ["fail", "error"]:
                    print(f"✗ {result['test']}")
                    print(f"  Details: {result['details']}")

        print("\n" + "=" * 70)

    def save_results(self) -> None:
        """Save test results to JSON file."""
        output_file = project_root / "test_results.json"
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "summary": {
                "passed": sum(1 for r in self.results if r["status"] == "pass"),
                "failed": sum(1 for r in self.results if r["status"] == "fail"),
                "errors": sum(1 for r in self.results if r["status"] == "error"),
                "skipped": sum(1 for r in self.results if r["status"] == "skip"),
                "total": len(self.results),
            },
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\nResults saved to: {output_file}")

    def run_all_tests(self) -> bool:
        """Run all tests."""
        print("\n" + "=" * 70)
        print("NEXUS API COMPREHENSIVE TEST SUITE")
        print(f"Started: {datetime.now().isoformat()}")
        print("=" * 70)

        self.test_env_keys()
        self.test_polygon_api()
        self.test_openrouter_api()
        self.test_deepseek_api()
        self.test_coingecko_api()
        self.test_nexus_data_api()

        self.print_summary()
        self.save_results()

        # Return success if no failures or errors
        failed = sum(1 for r in self.results if r["status"] == "fail")
        errors = sum(1 for r in self.results if r["status"] == "error")
        return failed == 0 and errors == 0


if __name__ == "__main__":
    tester = APITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
