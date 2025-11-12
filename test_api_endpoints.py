#!/usr/bin/env python3
"""Quick test of market API endpoints."""

import requests
import sys

BASE_URL = "http://localhost:8000"

def test_endpoints():
    """Test all market API endpoints."""
    
    tests = [
        ("Health Check", "GET", "/health", None),
        ("Status", "GET", "/api/v1/status", None),
        ("List Symbols", "GET", "/api/v1/symbols", None),
        ("Historical Data", "GET", "/api/v1/historical/AAPL", {"start": "2024-01-01", "end": "2024-03-31"}),
        ("Metrics", "GET", "/api/v1/metrics", None),
    ]
    
    results = []
    for name, method, endpoint, params in tests:
        try:
            url = f"{BASE_URL}{endpoint}"
            if method == "GET":
                resp = requests.get(url, params=params, timeout=5)
            else:
                resp = requests.post(url, json=params, timeout=5)
            
            status = "✓" if resp.status_code < 400 else "✗"
            results.append({
                "name": name,
                "endpoint": endpoint,
                "status": resp.status_code,
                "success": resp.status_code < 400
            })
            print(f"{status} {name}: {resp.status_code}")
            
            if resp.status_code < 400:
                data = resp.json()
                if "data" in data:
                    if isinstance(data["data"], list):
                        print(f"  └─ Got {len(data['data'])} records")
                    else:
                        print(f"  └─ Got data response")
                
        except Exception as e:
            results.append({
                "name": name,
                "endpoint": endpoint,
                "status": "error",
                "success": False
            })
            print(f"✗ {name}: {str(e)}")
    
    print("\n" + "="*60)
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"RESULTS: {passed}/{total} endpoints working")
    
    return all(r["success"] for r in results)

if __name__ == "__main__":
    success = test_endpoints()
    sys.exit(0 if success else 1)
