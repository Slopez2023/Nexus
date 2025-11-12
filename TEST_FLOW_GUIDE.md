# Warehouse API Integration - Complete Test Flow Guide

## Overview

This guide walks through the complete end-to-end flow for testing the Warehouse API integration with a live trading strategy.

**File**: `test_warehouse_strategy_flow.py`

---

## The Flow: 6 Steps

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Configuration                                           │
│ Load app config, verify settings                                │
└─────────────────────┬───────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Data Manager Initialization                             │
│ Create DataManager with all available sources                   │
└─────────────────────┬───────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Data Fetching                                           │
│ DataManager tries sources in priority order:                    │
│   1. Local CSV files (if exist)                                 │
│   2. Warehouse API (http://localhost:8000) ← NEW                │
│   3. Polygon.io (if API key available)                          │
│   4. YFinance (fallback)                                        │
│   5. CoinGecko (crypto fallback)                                │
└─────────────────────┬───────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Optional Source Comparison                              │
│ Compare Warehouse API data vs legacy sources                    │
│ Validate OHLCV consistency, latency, quality                    │
└─────────────────────┬───────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Strategy Execution                                      │
│ Initialize strategy (Golden Cross MA crossover)                 │
│ Generate trading signals from OHLCV data                        │
└─────────────────────┬───────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Validation Summary                                      │
│ Verify all components worked correctly                          │
│ Print metrics and recommendations                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. Database Running
```bash
# Option A: Local PostgreSQL
brew services start postgresql@15
psql -d nexus_trading -c "SELECT 1"

# Option B: Docker
docker-compose up -d db
```

### 2. Warehouse API Running
```bash
# Option A: Local (separate terminal)
cd ../Market-Data-Warehouse-API
python main.py
# Listens on http://localhost:8000

# Option B: Docker
docker run -p 8000:8000 warehouse-api:latest
```

### 3. Environment Setup
```bash
cd /path/to/nexus
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuration
```bash
# Copy example config
cp .env.example .env

# Verify these settings:
# WAREHOUSE_API_URL=http://localhost:8000
# WAREHOUSE_API_ENABLED=true
# WAREHOUSE_API_TIMEOUT=30
```

---

## Running the Test Flow

### Basic Usage (Default: AAPL, Jan-Mar 2024)
```bash
python test_warehouse_strategy_flow.py
```

### Custom Symbol and Date Range
```bash
python test_warehouse_strategy_flow.py \
  --symbol MSFT \
  --start 2024-01-01 \
  --end 2024-03-31
```

### Compare Warehouse API vs Legacy Sources
```bash
python test_warehouse_strategy_flow.py \
  --symbol AAPL \
  --compare
```

### Test Fallback (No Warehouse API)
```bash
python test_warehouse_strategy_flow.py \
  --no-warehouse
```

### Cryptocurrency Example
```bash
python test_warehouse_strategy_flow.py \
  --symbol BTC/USD \
  --start 2024-01-01 \
  --end 2024-03-31
```

---

## Expected Output

### Successful Flow Output
```
================================================================================
NEXUS WAREHOUSE API INTEGRATION TEST FLOW
================================================================================
Configuration: symbol=AAPL, period=2024-01-01 to 2024-03-31
Use Warehouse API: True
Compare sources: False

[1/6] Initializing configuration...
✓ Configuration loaded: environment=development

[2/6] Initializing DataManager...
✓ Warehouse API available: True

[3/6] Fetching data for AAPL...
✓ Fetched 64 candles
  Date range: 2024-01-02 09:30:00 to 2024-03-29 16:00:00
  Columns: Open, High, Low, Close, Volume
  Price range: 192.53 - 206.85

[4/6] Skipping source comparison (--compare not set)

[5/6] Generating trading signals...
✓ Strategy initialized: Golden Cross (MA Crossover)
✓ Generated 8 signals
  - Long signals: 4
  - Short signals: 4
  - Average confidence: 72.5%

  First signal: 2024-01-15 09:30:00 - LONG @ 68.5% confidence
  Last signal: 2024-03-22 09:30:00 - SHORT @ 76.2% confidence

[6/6] Validation Summary
✓ All components operational:
  - Configuration: OK
  - Data Pipeline: OK (64 candles)
  - Strategy Engine: OK
  - Signal Generation: OK (8 signals)
  - Warehouse API: OK

================================================================================
FLOW VALIDATION COMPLETE
================================================================================
Status: SUCCESS ✓
Symbol: AAPL
Period: 64 trading days
Signals: 8 generated
Warehouse API: Used
```

---

## Understanding the Test Strategy: Golden Cross

The test strategy uses a simple **Moving Average Crossover** approach:

### Signal Generation Logic
```
1. Calculate 20-day fast moving average
2. Calculate 50-day slow moving average
3. When fast MA crosses above slow MA → BUY signal (LONG)
4. When fast MA crosses below slow MA → SELL signal (SHORT)
```

### Confidence Scoring
```
Confidence = 0.6 + (MA_diff / Close_price) * 0.3

Range: 0.6 (minimum) to 0.9 (capped at max)
- Larger MA spread = Higher confidence
- Closer MAs = Lower confidence
```

### Why This Strategy?
- **Simple**: Easy to understand and validate
- **Deterministic**: Same inputs always produce same outputs
- **Effective**: Captures trend changes reliably
- **Production-Ready**: Demonstrates real strategy implementation

---

## Data Flow Details

### Step 3: Data Fetching Under the Hood

When you call `fetch_historical_data_async`:

```
DataManager.fetch_historical_data_async(symbol='AAPL', ...)
    ↓
Try source #0: LocalOHLCVDataSource
    ├─ Check if local CSV exists
    ├─ If found → return data
    └─ If not → continue
    ↓
Try source #0.5: WarehouseDataSource (NEW!)
    ├─ Check Warehouse API health
    ├─ Send HTTP GET /api/v1/historical/AAPL?start=...&end=...
    ├─ Receive normalized OHLCV JSON
    ├─ Validate data integrity
    ├─ Calculate quality score
    ├─ If healthy → return DataFrame
    └─ If unhealthy → continue to fallback
    ↓
Try source #1: MassiveDataSource (Polygon.io)
    ├─ If API key available → query Polygon
    └─ Continue chain if fail
    ↓
Try source #2: YFinanceDataSource
    ├─ Query Yahoo Finance
    └─ Last resort before error
    ↓
Return data from first successful source
```

### Warehouse API Integration Points

#### Client Layer (`warehouse_api_client.py`)
```python
client = WarehouseAPIClient(config.api.warehouse_api)
response = await client.get_historical_data(
    symbol='AAPL',
    start_date='2024-01-01',
    end_date='2024-03-31',
    timeframe='day'
)
# Returns: DataResponse with status, data, error, metrics
```

#### Adapter Layer (`warehouse_api_adapter.py`)
```python
adapter = WarehouseAPIAdapter()
df = adapter.adapt_historical_data(response_data, 'AAPL')
# Transforms API JSON → pandas DataFrame
# Validates OHLCV integrity
# Calculates quality score (0.0-1.0)
```

#### Monitor Layer (`warehouse_api_monitor.py`)
```python
monitor = WarehouseAPIMonitor()
monitor.record_request(success=True, response_time_ms=245)
health = monitor.get_health()
# Tracks: HEALTHY, DEGRADED, UNHEALTHY
# Decides: should we fallback?
```

---

## Interpreting Results

### Key Metrics in Output

#### Data Metrics
- **rows**: Number of candles fetched
- **date_range**: First and last trading date
- **price_range**: Min/max close price in period
- **quality_score**: Data quality 0.0-1.0
  - 1.0 = Perfect (100% complete, all OHLCV valid)
  - 0.8-0.99 = Good (>95% valid)
  - 0.5-0.79 = Acceptable (>80% valid)
  - <0.5 = Poor (needs investigation)

#### Signal Metrics
- **total**: Total signals generated
- **long**: Buy signals (uptrend starts)
- **short**: Sell signals (downtrend starts)
- **avg_confidence**: Average signal confidence (0.0-1.0)
  - >0.8 = High confidence trades
  - 0.6-0.8 = Medium confidence
  - <0.6 = Lower confidence trades

#### Warehouse API Metrics
- **warehouse_available**: API responded successfully
- **latency**: Response time in milliseconds
- **fallback_used**: Fallback was needed (API unavailable)

---

## Troubleshooting

### "Warehouse API not available"
```
Solution:
1. Start the Warehouse API server
2. Verify it's listening: curl http://localhost:8000/api/v1/health
3. Check WAREHOUSE_API_URL in .env
4. Script will automatically fallback to legacy sources
```

### "No data returned"
```
Solution:
1. Check symbol spelling (case-sensitive)
2. Verify date range is valid and has data
3. Check API logs for data source issues
4. Try with different symbol/date range
```

### "Data quality score too low"
```
Solution:
1. This is expected for some assets/periods
2. Check Warehouse API logs
3. Quality < 0.9 triggers warning in logs
4. System still processes but logs it
```

### "Connection refused"
```
Solution:
1. Verify all services running:
   - PostgreSQL: psql -d nexus_trading -c "SELECT 1"
   - Warehouse API: curl http://localhost:8000/api/v1/health
2. Check .env WAREHOUSE_API_URL
3. Run with --no-warehouse to skip Warehouse API
```

---

## What Gets Validated

### Configuration ✓
- Config file loads correctly
- Environment variables override defaults
- All required settings present

### Data Pipeline ✓
- DataManager initializes with all sources
- Warehouse API source registered at priority 0.5
- Fallback chain works properly

### Data Quality ✓
- OHLCV integrity: High ≥ Low ≥ Close
- Timestamp ordering: chronological
- No NaN or negative values
- Data gaps detected and logged

### Strategy Execution ✓
- Parameters validated at init
- Strategy metadata complete
- Signal generation deterministic
- Confidence scoring working

### Warehouse API Integration ✓
- Client connects successfully
- Adapter validates responses
- Monitor tracks health
- Fallback works on error

---

## Advanced Options

### Enabling Detailed Logging
```bash
# Set log level to DEBUG
NEXUS_LOG_LEVEL=DEBUG python test_warehouse_strategy_flow.py
```

### Custom Strategy Parameters
Edit the strategy initialization:
```python
# In the test file, change:
strategy = TestSimpleStrategyFlow(fast_window=20, slow_window=50)

# To test different parameters:
strategy = TestSimpleStrategyFlow(fast_window=10, slow_window=30)
```

### Testing Multiple Symbols
```bash
for symbol in AAPL MSFT GOOGL; do
    python test_warehouse_strategy_flow.py --symbol $symbol
done
```

### Stress Test (Long Period)
```bash
python test_warehouse_strategy_flow.py \
  --symbol AAPL \
  --start 2020-01-01 \
  --end 2024-03-31
```

---

## Next Steps After Validation

1. **If successful**: 
   - Integration is working correctly
   - Ready to use Warehouse API in production
   - Can move to Phase 4 (enable by default)

2. **If issues found**:
   - Review error logs
   - Check Warehouse API logs
   - Verify data format in adapter

3. **Production Deployment**:
   - Set `WAREHOUSE_API_PRIMARY=true` in .env
   - Run integration tests: `pytest tests/integration/`
   - Monitor metrics for 7 days
   - Gradually roll out to live trading

---

## Architecture Summary

```
Application
    ↓
[Strategy] → Requests OHLCV Data
    ↓
[DataManager] → Selects Data Source
    ↓
Priority Order:
  1. Local CSV
  2. WarehouseDataSource ← This is being tested
     ├─ WarehouseAPIClient (HTTP communication)
     ├─ WarehouseAPIAdapter (validation & transformation)
     └─ WarehouseAPIMonitor (health tracking)
  3. Polygon.io (MassiveDataSource)
  4. YFinance
  5. CoinGecko
    ↓
[Market Data Warehouse API] ← http://localhost:8000
    ↓
Returns normalized OHLCV data
    ↓
[Strategy] → Generates signals
    ↓
Output: Buy/Sell decisions with confidence scores
```

---

## Key Files for This Flow

| File | Purpose |
|------|---------|
| `test_warehouse_strategy_flow.py` | This test script (entry point) |
| `src/nexus/core/data/data.py` | DataManager with WarehouseDataSource |
| `src/nexus/integrations/warehouse_api_client.py` | HTTP client with retry/circuit breaker |
| `src/nexus/integrations/warehouse_api_adapter.py` | Response validation & transformation |
| `src/nexus/integrations/warehouse_api_monitor.py` | Health monitoring |
| `src/nexus/strategies/base.py` | Strategy base class |
| `.env` | Configuration (warehouse API settings) |

---

## Questions?

Refer to:
- `API_INTEGRATION_SUMMARY.md` - Quick reference
- `WAREHOUSE_API_INTEGRATION_PROGRESS.md` - Detailed progress
- `docs/WAREHOUSE_API_IMPLEMENTATION.md` - Usage guide

---

**Status**: Test flow ready for execution  
**Last Updated**: November 10, 2025  
**Integration Phase**: Complete (Phase 3 validated)
