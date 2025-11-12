# Warehouse API Integration - Flow Checklist

## Pre-Flight Checklist

Before running the test flow, verify all prerequisites:

### Infrastructure
- [ ] PostgreSQL running: `psql -d nexus_trading -c "SELECT 1"`
- [ ] Warehouse API running: `curl http://localhost:8000/api/v1/health`
- [ ] Network connectivity between services

### Code Setup
- [ ] Python 3.11+ installed: `python --version`
- [ ] Virtual environment activated: `source venv/bin/activate`
- [ ] Dependencies installed: `pip list | grep pandas`
- [ ] Current directory is project root

### Configuration
- [ ] `.env` file exists: `ls -la .env`
- [ ] Warehouse API URL configured: `grep WAREHOUSE_API_URL .env`
- [ ] Warehouse API enabled: `grep WAREHOUSE_API_ENABLED .env`

---

## Running the Test Flow

### Option 1: Basic Test (Recommended First Run)
```bash
python test_warehouse_strategy_flow.py
```
**What it tests**: AAPL, Jan-Mar 2024, uses Warehouse API if available

**Expected**: ✓ SUCCESS with ~60-70 signals generated

### Option 2: Custom Symbol
```bash
python test_warehouse_strategy_flow.py --symbol MSFT --start 2024-02-01 --end 2024-03-31
```
**What it tests**: Different symbol and date range

**Expected**: ✓ SUCCESS (adjust expected signals based on symbol volatility)

### Option 3: Compare Sources
```bash
python test_warehouse_strategy_flow.py --compare
```
**What it tests**: Warehouse API data vs legacy sources (YFinance, Polygon)

**Expected**: ✓ SUCCESS with source comparison metrics

### Option 4: No Warehouse API (Fallback Test)
```bash
python test_warehouse_strategy_flow.py --no-warehouse
```
**What it tests**: System works without Warehouse API (uses legacy sources)

**Expected**: ✓ SUCCESS with YFinance/Polygon data

### Option 5: Stress Test (Long History)
```bash
python test_warehouse_strategy_flow.py --symbol AAPL --start 2023-01-01 --end 2024-03-31
```
**What it tests**: Larger dataset, more signals, performance under load

**Expected**: ✓ SUCCESS with 200+ signals over 1+ year

---

## Success Criteria

Each run should produce all of these:

### ✓ Configuration Loaded
```
✓ Configuration loaded: environment=development
```

### ✓ DataManager Ready
```
✓ Warehouse API available: True  (or False if API down)
```

### ✓ Data Fetched
```
✓ Fetched 64 candles
  Date range: 2024-01-02 to 2024-03-29
  Columns: Open, High, Low, Close, Volume
  Price range: 192.53 - 206.85
```

### ✓ Signals Generated
```
✓ Generated 8 signals
  - Long signals: 4
  - Short signals: 4
  - Average confidence: 72.5%
```

### ✓ Final Summary
```
Status: SUCCESS ✓
Symbol: AAPL
Period: 64 trading days
Signals: 8 generated
Warehouse API: Used
```

---

## Common Issues & Quick Fixes

### Issue: "Connection refused"
```bash
# Fix: Start Warehouse API
cd ../Market-Data-Warehouse-API
python main.py

# Or verify it's running
curl http://localhost:8000/api/v1/health
```

### Issue: "No module named 'nexus'"
```bash
# Fix: Ensure src is in Python path
cd /path/to/nexus
python test_warehouse_strategy_flow.py  # From project root

# Or check PYTHONPATH
echo $PYTHONPATH
```

### Issue: "Database connection error"
```bash
# Fix: Start PostgreSQL
brew services start postgresql@15

# Verify:
psql -d nexus_trading -c "SELECT 1"
```

### Issue: "symbol not found" (no data)
```bash
# Fix: Try different symbol or date range
python test_warehouse_strategy_flow.py --symbol MSFT --start 2024-01-01

# Verify data exists in Warehouse API
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-03-31"
```

### Issue: "Warehouse API unavailable"
```bash
# This is OK - system falls back to YFinance/Polygon
# But verify with:
curl http://localhost:8000/api/v1/health

# Or run without Warehouse API
python test_warehouse_strategy_flow.py --no-warehouse
```

---

## Understanding the Output

### Data Section
```
✓ Fetched 64 candles
  Date range: 2024-01-02 to 2024-03-29      ← Full trading period
  Columns: Open, High, Low, Close, Volume   ← Required for strategy
  Price range: 192.53 - 206.85              ← Data looks reasonable
```

**What to look for**:
- ✓ Dates make sense
- ✓ All 5 OHLCV columns present
- ✓ Close between High and Low
- ✓ No extreme outliers

### Signals Section
```
✓ Generated 8 signals
  - Long signals: 4       ← Buy signals
  - Short signals: 4      ← Sell signals
  - Average confidence: 72.5%  ← Quality of signals
```

**What to look for**:
- ✓ Non-zero signal count
- ✓ Mix of long and short
- ✓ Confidence between 60-90%

---

## Step-by-Step Guide

### 1. Start Services (if not running)
```bash
# Terminal 1: PostgreSQL
brew services start postgresql@15

# Terminal 2: Warehouse API
cd ../Market-Data-Warehouse-API
python main.py

# Terminal 3: Test Flow
cd /path/to/nexus
source venv/bin/activate
```

### 2. Verify Everything is Ready
```bash
# Check PostgreSQL
psql -d nexus_trading -c "SELECT 1"
# Expected: 1 row

# Check Warehouse API
curl http://localhost:8000/api/v1/health
# Expected: {"status": "healthy"}

# Check Python setup
python --version
# Expected: Python 3.11+
```

### 3. Run the Test
```bash
python test_warehouse_strategy_flow.py
```

### 4. Monitor Output
```
Watch for:
✓ All 6 steps complete successfully
✓ No ERROR or EXCEPTION messages
✓ Final status: SUCCESS ✓
```

### 5. Review Results
```
Check metrics:
- Data quality score
- Number of signals
- Signal confidence
- Source used (Warehouse API or legacy)
```

---

## Performance Expectations

### Default Test (AAPL, Jan-Mar 2024)
- **Duration**: 5-15 seconds
- **Data fetched**: ~60-70 candles
- **Signals generated**: ~6-10
- **Memory usage**: <100MB
- **CPU**: Low (<5%)

### Stress Test (AAPL, 1-year history)
- **Duration**: 30-60 seconds
- **Data fetched**: ~250 candles
- **Signals generated**: ~30-50
- **Memory usage**: <200MB
- **CPU**: Moderate (10-20%)

### With Source Comparison
- **Duration**: 30-60 seconds (fetches 2+ sources)
- **Additional metric**: Warehouse vs YFinance correlation
- **Network**: Multiple API calls

---

## Next Steps

### After Successful Validation
1. **Review results** in console output
2. **Check logs** for any warnings: `tail -f nexus.log`
3. **Run integration tests**:
   ```bash
   pytest tests/integration/test_warehouse_api_integration.py -v
   ```
4. **Verify database** for data consistency:
   ```bash
   psql -d nexus_trading -c "SELECT * FROM data_cache LIMIT 1"
   ```

### Deployment Checklist
- [ ] Test flow passes: `python test_warehouse_strategy_flow.py`
- [ ] Integration tests pass: `pytest tests/integration/ -v`
- [ ] No ERROR messages in logs
- [ ] Data quality scores > 0.9
- [ ] Signals look reasonable (not too many false signals)
- [ ] Performance acceptable (< 30 seconds)

### Enable for Production
Once satisfied:
```bash
# Edit .env
WAREHOUSE_API_ENABLED=true
WAREHOUSE_API_PRIMARY=true  # After Phase 4 approval

# Restart services
systemctl restart nexus-api
# or
docker-compose restart
```

---

## Debug Mode

Run with detailed logging:
```bash
# Linux/Mac
NEXUS_LOG_LEVEL=DEBUG python test_warehouse_strategy_flow.py

# Windows
set NEXUS_LOG_LEVEL=DEBUG
python test_warehouse_strategy_flow.py
```

**Expect verbose output**:
- HTTP request/response details
- Data validation step-by-step
- Strategy parameter checks
- Signal generation details

---

## Contacts & Resources

- **Warehouse API Repo**: https://github.com/Slopez2023/Market-Data-Warehouse-API
- **Local API Docs**: http://localhost:8000/docs (Swagger UI)
- **Main Docs**: See `TEST_FLOW_GUIDE.md`
- **Config Docs**: See `.env.example`

---

**Last Updated**: November 10, 2025  
**Status**: Ready for testing  
**Integration Phase**: Complete (Phase 3)
