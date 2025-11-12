#!/usr/bin/env python3
"""Advanced API endpoint testing."""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_status():
    """Test API status endpoint."""
    print("\n" + "="*70)
    print("TEST: API Status")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/status", timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"Error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_symbols_list():
    """Test symbols endpoint."""
    print("\n" + "="*70)
    print("TEST: Available Symbols")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/symbols", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            if isinstance(data, dict) and "data" in data:
                symbols = data["data"]
            else:
                symbols = data
            
            print(f"Total symbols: {len(symbols)}")
            
            if isinstance(symbols, list) and len(symbols) > 0:
                print(f"\nFirst 10 symbols:")
                for sym in symbols[:10]:
                    if isinstance(sym, dict):
                        print(f"  - {sym.get('symbol', sym)}")
                    else:
                        print(f"  - {sym}")
            
            return True
        else:
            print(f"Error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_news():
    """Test news endpoint."""
    print("\n" + "="*70)
    print("TEST: News Endpoint")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/news/AAPL", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            if isinstance(data, dict):
                count = len(data.get("data", []))
            else:
                count = len(data)
            
            print(f"News articles found: {count}")
            
            if count > 0:
                if isinstance(data, dict) and "data" in data:
                    article = data["data"][0]
                else:
                    article = data[0]
                
                print(f"\nSample article:")
                print(f"  {json.dumps(article, indent=4)}")
            
            return True
        else:
            print(f"Status: {resp.status_code}")
            return False
    except Exception as e:
        print(f"Note: {e}")
        return False

def test_earnings():
    """Test earnings endpoint."""
    print("\n" + "="*70)
    print("TEST: Earnings Endpoint")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/earnings/AAPL", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"Status: {resp.status_code}")
            return False
    except Exception as e:
        print(f"Note: {e}")
        return False

def test_options_iv():
    """Test options IV endpoint."""
    print("\n" + "="*70)
    print("TEST: Options IV Endpoint")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/options/iv/AAPL", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"Status: {resp.status_code}")
            return False
    except Exception as e:
        print(f"Note: {e}")
        return False

def test_features():
    """Test features endpoint."""
    print("\n" + "="*70)
    print("TEST: ML Features Endpoint")
    print("="*70)
    
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/features/composite/AAPL", timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            if isinstance(data, dict):
                print(f"Feature categories: {list(data.keys())}")
                
                # Print sample of first feature
                if data:
                    first_key = list(data.keys())[0]
                    print(f"\nSample features from '{first_key}':")
                    print(f"  {json.dumps(data[first_key], indent=4)}")
            
            return True
        else:
            print(f"Status: {resp.status_code}")
            return False
    except Exception as e:
        print(f"Note: {e}")
        return False

def test_multiple_symbols():
    """Test multiple symbols."""
    print("\n" + "="*70)
    print("TEST: Multiple Symbol Data Fetch")
    print("="*70)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "META"]
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)
    
    params = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
    }
    
    print(f"Fetching data for: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}\n")
    
    results = {}
    for symbol in symbols:
        try:
            resp = requests.get(
                f"{BASE_URL}/api/v1/historical/{symbol}",
                params=params,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("data", []))
                print(f"✓ {symbol:10} -> {count} records")
                results[symbol] = count
            else:
                print(f"✗ {symbol:10} -> Status {resp.status_code}")
                results[symbol] = 0
        except Exception as e:
            print(f"✗ {symbol:10} -> Error: {str(e)}")
            results[symbol] = 0
    
    print(f"\nTotal records retrieved: {sum(results.values())}")
    return all(v > 0 for v in results.values())

def test_cache_performance():
    """Test API cache performance."""
    print("\n" + "="*70)
    print("TEST: Cache Performance")
    print("="*70)
    
    try:
        symbol = "AAPL"
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        params = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        }
        
        # First request (cache miss)
        import time
        start = time.time()
        resp1 = requests.get(
            f"{BASE_URL}/api/v1/historical/{symbol}",
            params=params,
            timeout=10
        )
        time1 = time.time() - start
        
        # Second request (cache hit)
        start = time.time()
        resp2 = requests.get(
            f"{BASE_URL}/api/v1/historical/{symbol}",
            params=params,
            timeout=10
        )
        time2 = time.time() - start
        
        print(f"First request (cache miss):  {time1*1000:.2f}ms")
        print(f"Second request (cache hit):  {time2*1000:.2f}ms")
        
        if time2 < time1:
            improvement = ((time1 - time2) / time1) * 100
            print(f"Cache improvement: {improvement:.1f}% faster")
        
        return resp1.status_code == 200 and resp2.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all advanced tests."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " ADVANCED API ENDPOINT TESTS".center(68) + "║")
    print("║" + f" Base URL: {BASE_URL}".ljust(68) + "║")
    print("╚" + "="*68 + "╝")
    
    tests = [
        ("API Status", test_status),
        ("Available Symbols", test_symbols_list),
        ("News", test_news),
        ("Earnings", test_earnings),
        ("Options IV", test_options_iv),
        ("ML Features", test_features),
        ("Multiple Symbols", test_multiple_symbols),
        ("Cache Performance", test_cache_performance),
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
        status = "✓" if passed_test else "○"
        print(f"{status} {name}")
    
    print("="*70)
    print(f"Result: {passed}/{total} tests passed/working")

if __name__ == "__main__":
    main()
