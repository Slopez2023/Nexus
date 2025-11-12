#!/usr/bin/env python3
"""Test local NEXUS API endpoints."""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_api():
    """Test API endpoints."""
    
    endpoints = [
        ("/", "root"),
        ("/api", "api root"),
        ("/docs", "swagger docs"),
        ("/openapi.json", "openapi schema"),
        ("/api/v1", "v1 api root"),
        ("/api/v1/health", "health check"),
        ("/api/v1/sources", "data sources"),
    ]
    
    print("Testing NEXUS API endpoints:")
    print("=" * 70)
    
    for path, description in endpoints:
        try:
            url = f"{BASE_URL}{path}"
            resp = requests.get(url, timeout=5)
            
            status_str = "✓" if resp.status_code < 400 else "✗"
            print(f"{status_str} {path:30} -> {resp.status_code} ({description})")
            
            # Print a snippet of response for successful requests
            if resp.status_code < 400:
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        keys = list(data.keys())[:3]
                        print(f"  ├─ Keys: {', '.join(keys)}")
                except:
                    print(f"  ├─ Response: {resp.text[:100]}")
                    
        except Exception as e:
            print(f"✗ {path:30} -> ERROR: {str(e)}")

if __name__ == "__main__":
    test_api()
