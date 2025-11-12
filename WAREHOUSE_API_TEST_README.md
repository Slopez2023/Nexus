# Warehouse API Test Suite

## Overview

Complete test suite for the Market Data Warehouse API (`http://localhost:8000`). Validates all endpoints and API functionality.

## Configuration Status

✅ **API Configuration Updated**
- **Status**: `enabled: true`
- **Primary**: `primary: true` 
- **URL**: `http://localhost:8000`
- **Location**: `config.json` → `api.warehouse_api`

## Running Tests

```bash
python test_warehouse_api.py
```

## Test Coverage

### 1. **Root Health Check** (`GET /`)
- Verifies API is running
- Returns API info, version, and all available endpoints
- **Expected**: Status 200 ✓

### 2. **System Status** (`GET /api/v1/status`)
- Database metrics (symbols, records, validation rate)
- Data quality checks
- Scheduler status
- **Expected**: Status 200 ✓

### 3. **Available Symbols** (`GET /api/v1/symbols`)
- Lists all available trading symbols
- Symbol count and latest data info
- **Expected**: Status 200 ✓

### 4. **Historical Data** (`GET /api/v1/historical/{symbol}?start=YYYY-MM-DD&end=YYYY-MM-DD`)
- Fetches OHLCV data for specified symbols
- Test symbols: AAPL, MSFT, GOOGL, BTC, ETH
- Date range: 2024-01-01 to 2024-12-31
- **Note**: Returns 404 until data is loaded into database

### 5. **Metrics** (`GET /api/v1/metrics`)
- API performance metrics
- Request latency, cache hit rates
- **Note**: May have circuit breaker issues if API is handling errors

## Test Results

After running tests, results are saved to:
```
warehouse_api_test_results.json
```

Includes:
- Individual endpoint responses
- Latency measurements
- Error information
- Client metrics (requests, errors, circuit breaker state)

## API Endpoints Summary

### Public Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | API info & documentation |
| GET | `/health` | Health check |
| GET | `/api/v1/status` | System status & database metrics |
| GET | `/api/v1/symbols` | List available symbols |
| GET | `/api/v1/historical/{symbol}` | Historical OHLCV data |
| GET | `/api/v1/metrics` | API performance metrics |
| GET | `/api/v1/observability/metrics` | Observability metrics |
| GET | `/api/v1/observability/alerts` | Alert system status |
| GET | `/api/v1/performance/cache` | Cache statistics |
| GET | `/api/v1/performance/queries` | Query performance |
| GET | `/api/v1/performance/summary` | Performance summary |

### Admin Endpoints (Require X-API-Key Header)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/admin/symbols` | Add new symbol |
| GET | `/api/v1/admin/symbols` | List all symbols (detailed) |
| GET | `/api/v1/admin/symbols/{symbol}` | Get symbol details |
| PUT | `/api/v1/admin/symbols/{symbol}` | Update symbol configuration |
| DELETE | `/api/v1/admin/symbols/{symbol}` | Remove symbol |

## Test Data

### Available Symbols (to be loaded)
- **Crypto**: BTC, ETH, SOL, XRP, DOGE
- **Stocks**: AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, NFLX, AMD, BA

### Data Format
- **OHLCV**: Open, High, Low, Close, Volume
- **Validation**: Includes validation metadata and gap detection
- **Timeframe**: Daily data
- **Range**: Full 2024 historical data

## Client Features

The test suite uses a production-grade async HTTP client with:

- ✅ Async/await support with connection pooling
- ✅ Exponential backoff retry logic
- ✅ Circuit breaker pattern for fault tolerance
- ✅ Rate limiting
- ✅ Comprehensive request/response logging
- ✅ Automatic timeout handling
- ✅ Request latency tracking

## Configuration Details

From `config.json`:

```json
{
  "warehouse_api": {
    "url": "http://localhost:8000",
    "enabled": true,
    "primary": true,
    "timeout_seconds": 30,
    "max_connections": 100,
    "retry_max_attempts": 3,
    "retry_initial_backoff_ms": 100,
    "retry_max_backoff_ms": 30000,
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_timeout_seconds": 60
  }
}
```

### Configuration Options
- `timeout_seconds`: Request timeout (5-300 seconds)
- `max_connections`: Max concurrent connections
- `retry_max_attempts`: Max retry attempts (1-10)
- `circuit_breaker_failure_threshold`: Failures before opening circuit
- `circuit_breaker_timeout_seconds`: How long before testing recovery

## Integration with Nexus

Once data is loaded, the Warehouse API will be used as the primary data source for:
- Strategy backtesting
- Real-time data feeds
- Historical data analysis
- Risk management calculations

Use the client in your code:

```python
from nexus.integrations import WarehouseAPIClient, WarehouseAPIConfig

config = WarehouseAPIConfig(
    url="http://localhost:8000",
    timeout_seconds=30,
)

async with WarehouseAPIClient(config) as client:
    response = await client.get_historical_data(
        symbol="AAPL",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    if response.is_success:
        print(response.data)
```

## Troubleshooting

### API Connection Failed
- Verify API is running: `curl http://localhost:8000/`
- Check Docker container status if using containers
- Verify `config.json` URL is correct

### No Data Found (404)
- Data needs to be loaded into the database
- Check scheduler status: `/api/v1/status` → `data_quality.scheduler_status`
- Run data backfill job

### Circuit Breaker Open (503)
- Indicates multiple API failures
- Circuit breaker will automatically test recovery after timeout
- Check API logs for underlying errors

### Timeout Errors
- Check API performance metrics: `/api/v1/performance/summary`
- Increase `timeout_seconds` in config if needed
- Check network connectivity

## Next Steps

1. **Load Data**: Load historical data for test symbols into the database
2. **Validate Integration**: Run `test_warehouse_api.py` after data is loaded
3. **Monitor Performance**: Use `/api/v1/metrics` and observability endpoints
4. **Use in Strategies**: Update trading strategies to use Warehouse API as primary data source

## Documentation

API documentation available at: `http://localhost:8000/docs`

Dashboard available at: `http://localhost:8000/dashboard`
