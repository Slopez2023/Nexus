#!/usr/bin/env python3
"""Full API test suite."""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    print("\n" + "="*70)
    print("TEST: Health Check")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(json.dumps(data, indent=2))
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_root():
    """Test root endpoint."""
    print("\n" + "="*70)
    print("TEST: Root Endpoint")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(json.dumps(data, indent=2))
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_openapi_schema():
    """Test OpenAPI schema."""
    print("\n" + "="*70)
    print("TEST: OpenAPI Schema")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        
        print(f"API Title: {data.get('info', {}).get('title', 'N/A')}")
        print(f"API Version: {data.get('info', {}).get('version', 'N/A')}")
        print(f"API Description: {data.get('info', {}).get('description', 'N/A')}")
        
        paths = data.get('paths', {})
        print(f"\nAvailable Endpoints ({len(paths)}):")
        for path in sorted(paths.keys())[:20]:
            methods = list(paths[path].keys())
            print(f"  {path:40} -> {', '.join(methods)}")
        
        if len(paths) > 20:
            print(f"  ... and {len(paths) - 20} more")
        
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_historical_data():
    """Test historical data endpoint."""
    print("\n" + "="*70)
    print("TEST: Historical Data Endpoint")
    print("="*70)
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        params = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "symbol": "AAPL"
        }
        
        print(f"Fetching historical data for AAPL:")
        print(f"  Date range: {start_date} to {end_date}")
        
        # Try different possible endpoints
        endpoints = [
            "/api/v1/historical/AAPL",
            "/historical/AAPL",
            "/data/AAPL",
            "/api/v1/data/AAPL",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{BASE_URL}{endpoint}"
                resp = requests.get(url, params=params, timeout=10)
                
                if resp.status_code < 400:
                    print(f"\n✓ SUCCESS: {endpoint}")
                    print(f"  Status: {resp.status_code}")
                    data = resp.json()
                    
                    if "data" in data:
                        print(f"  Records returned: {len(data.get('data', []))}")
                    
                    print(f"  Response keys: {list(data.keys())}")
                    
                    # Print first record if available
                    if data.get("data"):
                        print(f"\n  Sample record:")
                        print(f"    {json.dumps(data['data'][0], indent=4)}")
                    
                    return True
                    
            except Exception as e:
                continue
        
        print(f"\n✗ No working historical data endpoint found")
        print(f"  Tried: {', '.join(endpoints)}")
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_symbols():
    """Test symbols endpoint."""
    print("\n" + "="*70)
    print("TEST: Symbols/Securities Endpoint")
    print("="*70)
    
    try:
        endpoints = [
            "/symbols",
            "/api/v1/symbols",
            "/tickers",
            "/securities",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{BASE_URL}{endpoint}"
                resp = requests.get(url, timeout=5)
                
                if resp.status_code < 400:
                    print(f"✓ {endpoint}")
                    data = resp.json()
                    
                    if isinstance(data, dict) and "data" in data:
                        print(f"  Records: {len(data.get('data', []))}")
                    elif isinstance(data, list):
                        print(f"  Records: {len(data)}")
                    
                    return True
                    
            except:
                continue
        
        print(f"✗ No symbols endpoint found")
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_metrics():
    """Test metrics endpoint."""
    print("\n" + "="*70)
    print("TEST: Metrics Endpoint")
    print("="*70)
    
    try:
        endpoints = [
            "/metrics",
            "/api/v1/metrics",
            "/stats",
            "/api/v1/stats",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{BASE_URL}{endpoint}"
                resp = requests.get(url, timeout=5)
                
                if resp.status_code < 400:
                    print(f"✓ {endpoint}")
                    data = resp.json()
                    print(json.dumps(data, indent=2))
                    return True
                    
            except:
                continue
        
        print(f"✗ No metrics endpoint found")
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_docs():
    """Test docs endpoint."""
    print("\n" + "="*70)
    print("TEST: Swagger UI Documentation")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✓ Swagger UI is available at http://localhost:8000/docs")
            return True
        else:
            print(f"✗ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " LOCAL NEXUS API TEST SUITE".center(68) + "║")
    print("║" + f" Base URL: {BASE_URL}".ljust(68) + "║")
    print("╚" + "="*68 + "╝")
    
    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("OpenAPI Schema", test_openapi_schema),
        ("Symbols", test_symbols),
        ("Historical Data", test_historical_data),
        ("Metrics", test_metrics),
        ("Documentation", test_docs),
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_test in results.items():
        status = "✓" if passed_test else "✗"
        print(f"{status} {name}")
    
    print("="*70)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! API is fully functional.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
    
    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
