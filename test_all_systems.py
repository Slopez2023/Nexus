#!/usr/bin/env python3
"""Complete API key and endpoint testing."""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Load environment variables
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()


class ComprehensiveAPITest:
    """Test all APIs and endpoints."""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def test_env_variables(self) -> None:
        """Test environment variables."""
        print("\n" + "=" * 80)
        print("1. TESTING ENVIRONMENT VARIABLES")
        print("=" * 80)

        required_keys = [
            "MASSIVE_API_KEY",
            "OPENROUTER_API_KEY",
            "DEEPSEEK_API_KEY",
            "COINGECKO_API_KEY",
        ]

        for key in required_keys:
            value = os.getenv(key)
            if value:
                preview = f"{value[:8]}...{value[-4:]}"
                print(f"✓ {key:25} -> {preview}")
                self.passed += 1
            else:
                print(f"✗ {key:25} -> NOT SET")
                self.failed += 1
            self.results.append({"test": f"Env: {key}", "status": "pass" if value else "fail"})

    def test_polygon_api(self) -> None:
        """Test Polygon/Massive API."""
        print("\n" + "=" * 80)
        print("2. TESTING POLYGON API (MASSIVE_API_KEY)")
        print("=" * 80)

        api_key = os.getenv("MASSIVE_API_KEY")
        if not api_key:
            print("✗ Skipped - API key not set")
            self.skipped += 1
            self.results.append({"test": "Polygon API", "status": "skip"})
            return

        try:
            url = f"https://api.polygon.io/v1/marketstatus?apikey={api_key}"
            print(f"Testing: GET {url[:60]}...")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                market = data.get("status", "unknown")
                print(f"✓ WORKING - Market status: {market}")
                self.passed += 1
                self.results.append({"test": "Polygon API", "status": "pass", "market": market})
            elif response.status_code == 401:
                print(f"✗ FAILED - API key unauthorized")
                self.failed += 1
                self.results.append({"test": "Polygon API", "status": "fail", "error": "Unauthorized"})
            else:
                print(f"✗ FAILED - Status {response.status_code}")
                self.failed += 1
                self.results.append({"test": "Polygon API", "status": "fail", "error": f"Status {response.status_code}"})
        except Exception as e:
            print(f"✗ ERROR - {str(e)}")
            self.failed += 1
            self.results.append({"test": "Polygon API", "status": "error", "error": str(e)})

    def test_openrouter_api(self) -> None:
        """Test OpenRouter API."""
        print("\n" + "=" * 80)
        print("3. TESTING OPENROUTER API")
        print("=" * 80)

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("✗ Skipped - API key not set")
            self.skipped += 1
            self.results.append({"test": "OpenRouter API", "status": "skip"})
            return

        try:
            url = "https://openrouter.ai/api/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            print(f"Testing: GET {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = len(data.get("data", []))
                print(f"✓ WORKING - {models} models available")
                self.passed += 1
                self.results.append({"test": "OpenRouter API", "status": "pass", "models": models})
            elif response.status_code == 401:
                print(f"✗ FAILED - API key unauthorized")
                self.failed += 1
                self.results.append({"test": "OpenRouter API", "status": "fail", "error": "Unauthorized"})
            else:
                print(f"✗ FAILED - Status {response.status_code}")
                self.failed += 1
                self.results.append({"test": "OpenRouter API", "status": "fail", "error": f"Status {response.status_code}"})
        except Exception as e:
            print(f"✗ ERROR - {str(e)}")
            self.failed += 1
            self.results.append({"test": "OpenRouter API", "status": "error", "error": str(e)})

    def test_deepseek_api(self) -> None:
        """Test DeepSeek API."""
        print("\n" + "=" * 80)
        print("4. TESTING DEEPSEEK API")
        print("=" * 80)

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("✗ Skipped - API key not set")
            self.skipped += 1
            self.results.append({"test": "DeepSeek API", "status": "skip"})
            return

        try:
            url = "https://api.deepseek.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            print(f"Testing: GET {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ WORKING")
                self.passed += 1
                self.results.append({"test": "DeepSeek API", "status": "pass"})
            elif response.status_code == 401:
                print(f"✗ FAILED - API key unauthorized")
                self.failed += 1
                self.results.append({"test": "DeepSeek API", "status": "fail", "error": "Unauthorized"})
            else:
                print(f"✗ FAILED - Status {response.status_code}")
                self.failed += 1
                self.results.append({"test": "DeepSeek API", "status": "fail", "error": f"Status {response.status_code}"})
        except Exception as e:
            print(f"✗ ERROR - {str(e)}")
            self.failed += 1
            self.results.append({"test": "DeepSeek API", "status": "error", "error": str(e)})

    def test_coingecko_api(self) -> None:
        """Test CoinGecko API."""
        print("\n" + "=" * 80)
        print("5. TESTING COINGECKO API")
        print("=" * 80)

        api_key = os.getenv("COINGECKO_API_KEY")
        if not api_key:
            print("✗ Skipped - API key not set")
            self.skipped += 1
            self.results.append({"test": "CoinGecko API", "status": "skip"})
            return

        try:
            url = "https://pro-api.coingecko.com/api/v3/ping"
            params = {"x_cg_pro_api_key": api_key}
            print(f"Testing: GET {url}")
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ WORKING")
                self.passed += 1
                self.results.append({"test": "CoinGecko API", "status": "pass"})
            elif response.status_code == 401:
                print(f"✗ FAILED - API key unauthorized")
                self.failed += 1
                self.results.append({"test": "CoinGecko API", "status": "fail", "error": "Unauthorized"})
            else:
                print(f"✗ FAILED - Status {response.status_code}")
                self.failed += 1
                self.results.append({"test": "CoinGecko API", "status": "fail", "error": f"Status {response.status_code}"})
        except Exception as e:
            print(f"✗ ERROR - {str(e)}")
            self.failed += 1
            self.results.append({"test": "CoinGecko API", "status": "error", "error": str(e)})

    def test_nexus_local_api(self) -> None:
        """Test NEXUS local API endpoints."""
        print("\n" + "=" * 80)
        print("6. TESTING LOCAL NEXUS API")
        print("=" * 80)

        base_url = "http://localhost:8000"
        endpoints = [
            ("/", "Root endpoint"),
            ("/health", "Health check"),
            ("/openapi.json", "OpenAPI schema"),
            ("/docs", "Swagger UI"),
        ]

        for path, description in endpoints:
            try:
                url = f"{base_url}{path}"
                print(f"Testing: GET {path:30} - {description}")
                
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    print(f"✓ {response.status_code} - Working")
                    self.passed += 1
                    self.results.append({"test": f"NEXUS: {description}", "status": "pass"})
                else:
                    print(f"✗ {response.status_code} - Failed")
                    self.failed += 1
                    self.results.append({"test": f"NEXUS: {description}", "status": "fail", "error": f"Status {response.status_code}"})
            except requests.exceptions.ConnectionError:
                print(f"✗ Connection refused - server not running")
                self.failed += 1
                self.results.append({"test": f"NEXUS: {description}", "status": "fail", "error": "Connection refused"})
            except Exception as e:
                print(f"✗ Error - {str(e)}")
                self.failed += 1
                self.results.append({"test": f"NEXUS: {description}", "status": "error", "error": str(e)})

    def print_summary(self) -> None:
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✓ Passed:  {self.passed}")
        print(f"✗ Failed:  {self.failed}")
        print(f"⊘ Skipped: {self.skipped}")
        print(f"━ Total:   {self.passed + self.failed + self.skipped}")
        print("=" * 80)

        if self.failed > 0:
            print("\n⚠️  ACTION REQUIRED:")
            print("   - Add API keys to .env file")
            print("   - Verify API key validity with respective providers")

        success_rate = (
            (self.passed / (self.passed + self.failed) * 100)
            if (self.passed + self.failed) > 0
            else 0
        )
        print(f"\nSuccess rate: {success_rate:.1f}%")

    def save_results(self) -> None:
        """Save test results."""
        output_file = project_root / "api_test_results.json"
        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "total": self.passed + self.failed + self.skipped,
            },
            "results": self.results,
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"\n📊 Results saved to: api_test_results.json")

    def run(self) -> bool:
        """Run all tests."""
        print("\n" + "╔" + "=" * 78 + "╗")
        print("║" + " " * 78 + "║")
        print("║" + " NEXUS TRADING SYSTEM - COMPREHENSIVE API KEY & ENDPOINT TEST".center(78) + "║")
        print("║" + " " * 78 + "║")
        print("╚" + "=" * 78 + "╝")

        self.test_env_variables()
        self.test_polygon_api()
        self.test_openrouter_api()
        self.test_deepseek_api()
        self.test_coingecko_api()
        self.test_nexus_local_api()

        self.print_summary()
        self.save_results()

        return self.failed == 0


if __name__ == "__main__":
    tester = ComprehensiveAPITest()
    success = tester.run()
    sys.exit(0 if success else 1)
