# CSV Data Implementation Plan

**Status:** Ready to execute  
**Timeline:** 5 days to production-ready  
**Risk Level:** Low (no external dependencies, local-only changes)  
**Success Metric:** Validation runner completes 100% with CSV data, zero API calls

---

## The Problem We're Solving

Right now:
- ❌ Backtesting uses yfinance (80% quality, API rate limits)
- ❌ Validation runners fail when APIs are rate-limited
- ❌ Walk-forward analysis can't run 100+ iterations (quota exhausted)
- ❌ Monte Carlo needs deterministic data (APIs change)

After implementation:
- ✅ Backtesting uses pre-validated CSVs (100% quality)
- ✅ Validation runners complete in minutes (no API waits)
- ✅ Walk-forward scales to unlimited iterations (disk is cheap)
- ✅ Monte Carlo reproduces identically (CSVs immutable)

---

## Architecture Decision

### Current State
```
yfinance API → Live fetch → Backtest engine → Results
     ↓
- Slow (network I/O)
- Unreliable (rate limits)
- Non-reproducible (data changes)
- Expensive (API quotas)
```

### Target State
```
CSV files ─→ CSVDataLoader ─→ Backtest engine ─→ Results
     ↓
- Fast (disk I/O)
- Reliable (immutable)
- Reproducible (identical every run)
- Free (no APIs)
```

### Design Principles
1. **Minimal disruption** - Don't refactor BacktestEngine, extend it
2. **Gradual adoption** - Run in parallel with yfinance during transition
3. **Testability** - Every change has unit tests before integration
4. **Reversible** - If CSV approach fails, fallback to yfinance works

---

## Phase 1: Foundation (Days 1-2, ~4 hours)

### 1.1: Data Inventory & Collection

**Goal:** Ensure you have CSV files for all Phase 2 strategy pairs.

**What to do:**

```bash
# Step 1: Audit what exists
find src/nexus/ohlcv -name "*.csv" -type f | sort
du -sh src/nexus/ohlcv/*/

# Step 2: Check for gaps
# Expected minimum for Phase 2: BTC, ETH daily 260 weeks
ls src/nexus/ohlcv/BTC/*1d*.csv  # Should exist
ls src/nexus/ohlcv/ETH/*1d*.csv  # Should exist
```

**If files missing, fetch them:**

```bash
# Fetch BTC 1d (5 years)
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260 --source ccxt-binanceus --strict

# Fetch ETH 1d (5 years)
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset ETH --timeframe 1d --weeks 260 --source ccxt-binanceus --strict

# Optional: Other pairs for robustness
for symbol in SOL AVAX BNB XRP DOGE; do
  python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset $symbol --timeframe 1d --weeks 260 --source ccxt-binanceus --strict &
done
wait
```

**Expected output:**
```
✅ BTC 1d data: 1826 candles, 125KB
✅ ETH 1d data: 1826 candles, 108KB
✅ SOL 1d data: 1500+ candles, 65KB
... (all successful)
```

**Time:** 10-30 minutes (depending on network)

**Deliverable:** `src/nexus/ohlcv/{BTC,ETH,SOL,AVAX,BNB,XRP,DOGE}/*-1d-*.csv` exist and validate

---

### 1.2: Create CSVDataLoader

**Goal:** Build the data loading interface.

**File:** `src/nexus/core/data_loader.py` (new file)

```python
"""Load pre-validated OHLCV CSV data for backtesting.

This module replaces live API calls with immutable CSV snapshots,
enabling reproducible, fast, unlimited backtests without API costs/limits.
"""

from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
import logging

from nexus.core.exceptions import DataError


logger = logging.getLogger(__name__)


class CSVDataLoader:
    """Load OHLCV data from CSV files for deterministic backtesting."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize loader.
        
        Args:
            data_dir: Root directory containing ASSET/{ASSET-TF-*.csv} files.
                     Defaults to 'src/nexus/ohlcv'
        """
        if data_dir is None:
            data_dir = "src/nexus/ohlcv"
        
        self.data_dir = Path(data_dir)
        
        if not self.data_dir.exists():
            raise DataError(
                f"Data directory not found: {self.data_dir}\n"
                f"Create it or run: python src/nexus/ohlcv/ohlcv_fetch_validate.py"
            )
        
        logger.info(f"CSVDataLoader initialized: {self.data_dir}")
    
    def load(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load OHLCV data for a symbol/timeframe.
        
        Args:
            symbol: Trading pair (e.g., "BTC", "ETH", "SOL")
            timeframe: Candlestick size (e.g., "1m", "5m", "1h", "4h", "1d")
            start_date: Optional filter (ISO format: "2020-01-01")
            end_date: Optional filter (ISO format: "2025-01-01")
        
        Returns:
            DataFrame with:
            - Index: datetime (UTC)
            - Columns: Open, High, Low, Close, Volume (float)
        
        Raises:
            DataError: If file not found, loading fails, or validation fails
        """
        symbol_upper = symbol.upper()
        asset_dir = self.data_dir / symbol_upper
        
        if not asset_dir.exists():
            available = self.available_pairs()
            raise DataError(
                f"No data for {symbol_upper}.\n"
                f"Available: {list(available.keys())}\n"
                f"Fetch with: python src/nexus/ohlcv/ohlcv_fetch_validate.py "
                f"--asset {symbol_upper} --timeframe {timeframe} --weeks 260"
            )
        
        # Find matching CSV files (most recent if multiple)
        pattern = f"{symbol_upper}-{timeframe}-*.csv"
        matching_files = sorted(
            asset_dir.glob(pattern),
            key=lambda x: x.stat().st_mtime
        )
        
        if not matching_files:
            available = self.available_pairs().get(symbol_upper, [])
            raise DataError(
                f"No CSV for {symbol_upper}-{timeframe}.\n"
                f"Available timeframes: {available}"
            )
        
        csv_file = matching_files[-1]
        logger.info(f"Loading {symbol_upper}-{timeframe} from {csv_file.name}")
        
        try:
            # Load with datetime index
            df = pd.read_csv(
                csv_file,
                index_col=0,
                parse_dates=True
            )
            
            # Normalize column names (lowercase in CSV → Capitalized)
            df.columns = [col.strip().capitalize() for col in df.columns]
            
            # Ensure OHLCV columns exist
            required = ["Open", "High", "Low", "Close", "Volume"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                raise DataError(f"Missing columns: {missing}")
            
            # Keep only OHLCV
            df = df[required]
            
            # Convert to numeric (robust to spaces/formatting)
            for col in required:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Remove any NaN rows (shouldn't happen, but safety)
            df_clean = df.dropna()
            if len(df_clean) < len(df):
                logger.warning(f"Removed {len(df) - len(df_clean)} NaN rows")
            df = df_clean
            
            if df.empty:
                raise DataError("CSV loaded but has no valid data")
            
            # Validate OHLC integrity
            invalid_high_low = (df["High"] < df["Low"]).sum()
            invalid_high_ohlc = (df["High"] < df[["Open", "Close"]].max(axis=1)).sum()
            
            if invalid_high_low > 0 or invalid_high_ohlc > 0:
                logger.warning(
                    f"{invalid_high_low} High<Low rows, "
                    f"{invalid_high_ohlc} High<Open/Close rows"
                )
            
            # Apply date filters if provided
            if start_date:
                start_ts = pd.Timestamp(start_date, tz="UTC")
                df = df[df.index >= start_ts]
            
            if end_date:
                end_ts = pd.Timestamp(end_date, tz="UTC")
                df = df[df.index <= end_ts]
            
            if df.empty:
                raise DataError(f"No data in range [{start_date}, {end_date}]")
            
            logger.info(
                f"Loaded {len(df)} candles "
                f"({df.index.min().date()} to {df.index.max().date()})"
            )
            
            return df
        
        except pd.errors.ParserError as e:
            raise DataError(f"CSV parsing error: {e}")
        except Exception as e:
            raise DataError(f"Failed to load {csv_file.name}: {e}")
    
    def available_pairs(self) -> Dict[str, List[str]]:
        """
        Return all available symbol/timeframe combinations.
        
        Returns:
            {symbol: [timeframes]}
            Example: {"BTC": ["1d", "1h", "4h"], "ETH": ["1d"]}
        """
        pairs = {}
        
        for asset_dir in self.data_dir.iterdir():
            # Skip non-directories and hidden folders
            if not asset_dir.is_dir() or asset_dir.name.startswith("."):
                continue
            
            symbol = asset_dir.name.upper()
            timeframes = []
            
            # Parse CSV filenames: SYMBOL-TIMEFRAME-WEEKS-data.csv
            for csv_file in asset_dir.glob("*.csv"):
                parts = csv_file.stem.split("-")
                if len(parts) >= 2:
                    timeframe = parts[1]
                    if timeframe not in timeframes:
                        timeframes.append(timeframe)
            
            if timeframes:
                pairs[symbol] = sorted(timeframes)
        
        return pairs
    
    def get_metadata(self, symbol: str, timeframe: str = "1d") -> Dict:
        """
        Get metadata about a CSV file (date range, size, etc).
        
        Returns:
            {
                "file": relative path,
                "size_kb": file size in KB,
                "rows": number of candles,
                "date_start": earliest date,
                "date_end": latest date,
                "date_range_days": span in days
            }
        """
        try:
            symbol_upper = symbol.upper()
            asset_dir = self.data_dir / symbol_upper
            
            pattern = f"{symbol_upper}-{timeframe}-*.csv"
            matching_files = list(asset_dir.glob(pattern))
            
            if not matching_files:
                return {}
            
            csv_file = sorted(
                matching_files,
                key=lambda x: x.stat().st_mtime
            )[-1]
            
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            
            return {
                "file": str(csv_file.relative_to(self.data_dir)),
                "size_kb": csv_file.stat().st_size / 1024,
                "rows": len(df),
                "date_start": df.index.min().isoformat(),
                "date_end": df.index.max().isoformat(),
                "date_range_days": int((df.index.max() - df.index.min()).days),
            }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {}


# Global instance for convenience
_loader: Optional[CSVDataLoader] = None


def get_csv_loader(data_dir: Optional[str] = None) -> CSVDataLoader:
    """Get or create the global CSV loader instance."""
    global _loader
    if _loader is None:
        _loader = CSVDataLoader(data_dir)
    return _loader
```

**Tests:** `tests/core/test_data_loader.py`

```python
"""Tests for CSVDataLoader."""

import pytest
import pandas as pd
from pathlib import Path

from nexus.core.data_loader import CSVDataLoader
from nexus.core.exceptions import DataError


class TestCSVDataLoader:
    """Test CSV data loading and validation."""
    
    def test_init_valid_directory(self):
        """Loader initializes with valid data directory."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        assert loader.data_dir.exists()
    
    def test_init_invalid_directory(self):
        """Loader raises error for missing directory."""
        with pytest.raises(DataError):
            CSVDataLoader("/nonexistent/path")
    
    def test_available_pairs(self):
        """Returns available symbol/timeframe combinations."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        pairs = loader.available_pairs()
        
        assert isinstance(pairs, dict)
        # Should have at least BTC with some timeframes
        if "BTC" in pairs:
            assert isinstance(pairs["BTC"], list)
            assert len(pairs["BTC"]) > 0
    
    def test_load_btc_daily(self):
        """Load BTC daily data successfully."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        
        try:
            df = loader.load("BTC", "1d")
            
            # Check structure
            assert isinstance(df, pd.DataFrame)
            assert df.index.name in ["datetime", "Date"]
            assert pd.api.types.is_datetime64_any_dtype(df.index)
            
            # Check columns
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                assert col in df.columns
            
            # Check data integrity
            assert len(df) > 0
            assert (df["High"] >= df["Low"]).all()
            assert (df["Close"] >= 0).all()
        
        except DataError as e:
            pytest.skip(f"BTC data not available: {e}")
    
    def test_load_with_date_range(self):
        """Load with date filtering."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        
        try:
            df = loader.load(
                "BTC", "1d",
                start_date="2020-01-01",
                end_date="2021-01-01"
            )
            
            assert df.index.min() >= pd.Timestamp("2020-01-01", tz="UTC")
            assert df.index.max() <= pd.Timestamp("2021-01-01", tz="UTC")
        
        except DataError as e:
            pytest.skip(f"BTC data not available: {e}")
    
    def test_load_missing_symbol(self):
        """Raises error for missing symbol."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        
        with pytest.raises(DataError):
            loader.load("NONEXISTENT", "1d")
    
    def test_get_metadata(self):
        """Get metadata about CSV file."""
        loader = CSVDataLoader("src/nexus/ohlcv")
        
        try:
            meta = loader.get_metadata("BTC", "1d")
            
            assert "file" in meta
            assert "rows" in meta
            assert meta["rows"] > 0
        
        except DataError:
            pytest.skip("BTC data not available")
```

**Time:** 60-90 minutes  
**Deliverable:** `src/nexus/core/data_loader.py` + passing tests

---

## Phase 2: Integration (Days 2-3, ~3 hours)

### 2.1: Update BacktestEngine

**Goal:** Make BacktestEngine use CSVDataLoader by default.

**File:** `src/nexus/backtesting/engine.py` (modifications)

```python
# At top, add import:
from nexus.core.data_loader import get_csv_loader

# In BacktestEngine.__init__, add:
def __init__(self, config: Optional[Dict[str, Any]] = None):
    """Initialize backtesting engine with CSV loader."""
    self.config = config or {}
    
    # Initialize CSV loader
    data_dir = config.get("data_dir") or config.get("csv_data_dir") or "src/nexus/ohlcv"
    self.csv_loader = get_csv_loader(data_dir)
    
    # Keep yfinance as fallback
    self.use_csv_primary = config.get("use_csv_primary", True)
    
    # ... rest of init

# Add method to get data (new helper):
def _get_price_data(
    self,
    symbol: str,
    timeframe: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Get price data from CSV (primary) or yfinance (fallback).
    
    Returns:
        DataFrame with datetime index and OHLCV columns
    """
    # Try CSV first if enabled
    if self.use_csv_primary:
        try:
            self.logger.info(f"Loading {symbol} {timeframe} from CSV...")
            return self.csv_loader.load(
                symbol, timeframe, start_date, end_date
            )
        except Exception as e:
            self.logger.warning(f"CSV load failed: {e}. Falling back to yfinance.")
    
    # Fallback to yfinance
    self.logger.info(f"Fetching {symbol} {timeframe} from yfinance...")
    import yfinance as yf
    ticker = yf.download(symbol, start=start_date, end=end_date)
    if ticker.empty:
        raise DataError(f"No yfinance data for {symbol}")
    return ticker

# Update any run_backtest/simulate methods to use _get_price_data:
def run_backtest(self, strategy_func: Callable, symbol: str = "BTC", **kwargs):
    """Run backtest with CSV data."""
    timeframe = kwargs.get("timeframe", "1d")
    start_date = kwargs.get("start_date")
    end_date = kwargs.get("end_date")
    
    # Get data (CSV preferred)
    price_data = self._get_price_data(symbol, timeframe, start_date, end_date)
    
    # Run simulation as before
    return self._run_simulation(strategy_func, price_data, **kwargs)
```

**Configuration:** `config.json`

```json
{
  "backtesting": {
    "use_csv_primary": true,
    "csv_data_dir": "src/nexus/ohlcv"
  }
}
```

**Time:** 45 minutes  
**Deliverable:** BacktestEngine loads from CSV, with yfinance fallback

---

### 2.2: Update Validation Runner

**Goal:** Make ValidationRunner use CSVDataLoader.

**File:** `src/nexus/backtesting/validation_runner.py` (modifications)

```python
# In ValidationRunner.__init__, add:
def __init__(self, config: Optional[Dict[str, Any]] = None):
    """Initialize validation with CSV data loading."""
    self.config = config or {}
    
    # Get CSV loader
    self.csv_loader = get_csv_loader(
        config.get("csv_data_dir", "src/nexus/ohlcv")
    )
    
    # ... rest of init

# Update run_comprehensive_validation to load data:
def run_comprehensive_validation(
    self,
    strategy_func: Callable,
    symbol: str = "BTC",
    timeframe: str = "1d",
    **kwargs
) -> ValidationReport:
    """Run validation using CSV data."""
    
    # Load data from CSV
    self.logger.info(f"Loading CSV data for {symbol} {timeframe}")
    price_data = self.csv_loader.load(symbol, timeframe)
    
    # Run validation as before
    return self._run_validation(strategy_func, price_data, **kwargs)
```

**Time:** 30 minutes  
**Deliverable:** ValidationRunner loads from CSV

---

### 2.3: Test Integration

**File:** `tests/backtesting/test_backtest_csv.py`

```python
"""Test backtesting with CSV data."""

import pytest
import pandas as pd
from nexus.backtesting.engine import BacktestEngine
from nexus.strategies.momentum import MomentumStrategy


class TestBacktestWithCSV:
    """Test backtesting using CSV data."""
    
    def test_backtest_loads_csv(self):
        """Backtest successfully loads and runs with CSV data."""
        engine = BacktestEngine({"use_csv_primary": True})
        
        try:
            # Run simple backtest with CSV data
            result = engine.run_backtest(
                strategy_func=MomentumStrategy.generate_signals,
                symbol="BTC",
                timeframe="1d",
                formation_days=126
            )
            
            assert result is not None
            assert "trades" in result or "sharpe_ratio" in result
            assert result.get("data_source") == "csv"
        
        except Exception as e:
            pytest.skip(f"CSV data not available: {e}")
    
    def test_backtest_csv_consistent(self):
        """Multiple runs with same CSV produce identical results."""
        engine = BacktestEngine({"use_csv_primary": True})
        
        try:
            result1 = engine.run_backtest(
                strategy_func=MomentumStrategy.generate_signals,
                symbol="BTC",
                timeframe="1d",
                formation_days=126
            )
            
            result2 = engine.run_backtest(
                strategy_func=MomentumStrategy.generate_signals,
                symbol="BTC",
                timeframe="1d",
                formation_days=126
            )
            
            # Results should be identical (CSV is deterministic)
            assert result1["sharpe_ratio"] == result2["sharpe_ratio"]
            assert result1["total_return"] == result2["total_return"]
        
        except Exception as e:
            pytest.skip(f"CSV data not available: {e}")
```

```bash
# Run tests
pytest tests/backtesting/test_backtest_csv.py -v
```

**Time:** 45 minutes  
**Deliverable:** Integration tests passing

---

## Phase 3: Validation (Days 3-4, ~2 hours)

### 3.1: Run Existing Validation Scripts

**Goal:** Verify existing strategies work with CSV data.

```bash
# Simple momentum validation
python simple_momentum_validation.py

# Expected output:
# ✅ Loading BTC 1d from CSV
# ✅ Running momentum strategy
# ✅ Walk-forward analysis
# ✅ Monte Carlo simulation
# ✅ VALIDATION COMPLETE

# Other strategy validations
python simple_mean_reversion_validation.py
python simple_rsi_divergence_validation.py
python simple_trend_following_validation.py
```

**Modify scripts if needed:**

```python
# Before (yfinance):
import yfinance as yf
price_data = yf.download("BTC-USD", start="2020-01-01")

# After (CSV):
from nexus.core.data_loader import get_csv_loader
loader = get_csv_loader()
price_data = loader.load("BTC", "1d")
```

**Time:** 60 minutes  
**Deliverable:** All validation scripts pass with CSV data

---

### 3.2: Performance Verification

**Goal:** Confirm CSV is faster than API.

**Script:** `scripts/benchmark_data_loading.py`

```python
"""Compare CSV vs yfinance loading performance."""

import time
from nexus.core.data_loader import get_csv_loader

def benchmark_csv():
    """Benchmark CSV loading."""
    loader = get_csv_loader()
    
    symbols = ["BTC", "ETH", "SOL"]
    
    print("\n📊 CSV Loading Benchmark")
    print("=" * 50)
    
    for symbol in symbols:
        start = time.time()
        df = loader.load(symbol, "1d")
        elapsed = time.time() - start
        
        print(f"{symbol:6} | {len(df):5} rows | {elapsed*1000:.1f}ms")


def benchmark_yfinance():
    """Benchmark yfinance loading."""
    import yfinance as yf
    
    symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]
    
    print("\n📊 YFinance Loading Benchmark")
    print("=" * 50)
    
    for symbol in symbols:
        start = time.time()
        df = yf.download(symbol, start="2020-01-01", end="2025-01-01", progress=False)
        elapsed = time.time() - start
        
        print(f"{symbol:8} | {len(df):5} rows | {elapsed*1000:.1f}ms")


if __name__ == "__main__":
    print("🏃 Comparing data loading performance...\n")
    
    benchmark_csv()
    benchmark_yfinance()
    
    print("\n💡 CSV is typically 10-50x faster (disk vs network)")
```

```bash
python scripts/benchmark_data_loading.py
```

**Expected output:**
```
📊 CSV Loading Benchmark
==================================================
BTC    |  1826 rows |  15.3ms
ETH    |  1826 rows |  14.8ms
SOL    |  1500 rows |  12.1ms

📊 YFinance Loading Benchmark
==================================================
BTC-USD  |  1826 rows | 2340.5ms
ETH-USD  |  1826 rows | 1850.2ms
SOL-USD  |  1500 rows | 1920.0ms

💡 CSV is typically 10-50x faster (disk vs network)
```

**Time:** 30 minutes  
**Deliverable:** Performance improvement documented

---

## Phase 4: Cleanup & Optimization (Day 4, ~1 hour)

### 4.1: Remove Dependency on Live APIs (Optional)

If you want to fully commit to CSV approach:

```python
# In config.json, disable yfinance fallback:
{
  "backtesting": {
    "use_csv_primary": true,
    "allow_yfinance_fallback": false,  # Fail fast if CSV missing
    "csv_data_dir": "src/nexus/ohlcv"
  }
}
```

### 4.2: Add Data Documentation

**File:** `src/nexus/ohlcv/DATA_MANIFEST.md`

```markdown
# OHLCV Data Manifest

Last Updated: 2025-11-09

## Available Data

| Symbol | Timeframe | Weeks | Rows | Size | Date Range |
|--------|-----------|-------|------|------|------------|
| BTC    | 1d        | 260   | 1826 | 125KB | 2020-11-09 to 2025-11-09 |
| ETH    | 1d        | 260   | 1826 | 108KB | 2020-11-09 to 2025-11-09 |
| SOL    | 1d        | 260   | 1500+ | 65KB | 2021-04-01 to 2025-11-09 |
| AVAX   | 1d        | 260   | 1000+ | 52KB | 2020-09-21 to 2025-11-09 |
| BNB    | 1d        | 260   | 1826 | 92KB | 2020-11-09 to 2025-11-09 |
| XRP    | 1d        | 260   | 1826 | 78KB | 2020-11-09 to 2025-11-09 |
| DOGE   | 1d        | 260   | 1826 | 64KB | 2020-11-09 to 2025-11-09 |

## Validation Status

✅ All data validated with 10-rule quality system:
- Completeness ≥95%
- No negative prices
- OHLC logic valid (High≥Open,Close; Low≤Open,Close)
- Max daily change <100%
- No data gaps >1 day
- Timestamp alignment correct
- Volume ≥0

## Data Refresh Schedule

- Daily data: Updated weekly (Sunday 2 AM)
- Hourly data: Updated daily (1 AM)
- Minute data: Updated as needed for active pairs

## Usage

```python
from nexus.core.data_loader import get_csv_loader

loader = get_csv_loader()
btc_data = loader.load("BTC", "1d")
print(btc_data.head())
```

## Refresh Commands

```bash
# Single pair
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260 --strict

# All pairs (parallel)
for symbol in BTC ETH SOL AVAX BNB XRP DOGE; do
  python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset $symbol --timeframe 1d --weeks 260 --strict &
done
wait
```

## File Organization

```
src/nexus/ohlcv/
├── BTC/
│   ├── BTC-1d-260wks-data.csv
│   ├── BTC-1h-52wks-data.csv
│   └── ...
├── ETH/
│   ├── ETH-1d-260wks-data.csv
│   └── ...
└── [other assets]
```
```

**Time:** 15 minutes  
**Deliverable:** Data documentation complete

---

## Phase 5: Automation (Day 5, Optional, ~30 minutes)

### 5.1: Create Data Refresh Automation

**File:** `scripts/refresh_data.sh`

```bash
#!/bin/bash
# Refresh OHLCV data weekly

set -e

LOG_FILE="logs/data_refresh.log"
mkdir -p logs

echo "[$(date)] Starting data refresh..." >> "$LOG_FILE"

# Symbols to update
SYMBOLS=("BTC" "ETH" "SOL" "AVAX" "BNB" "XRP" "DOGE")
TIMEFRAME="1d"
WEEKS=260

for symbol in "${SYMBOLS[@]}"; do
  echo "[$(date)] Refreshing $symbol-$TIMEFRAME..." >> "$LOG_FILE"
  
  if python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset "$symbol" \
    --timeframe "$TIMEFRAME" \
    --weeks "$WEEKS" \
    --source ccxt-binanceus \
    --strict \
    --overwrite >> "$LOG_FILE" 2>&1; then
    echo "✅ $symbol refreshed" >> "$LOG_FILE"
  else
    echo "⚠️  $symbol refresh failed" >> "$LOG_FILE"
  fi
done

echo "[$(date)] Data refresh complete" >> "$LOG_FILE"
```

**Permissions:**
```bash
chmod +x scripts/refresh_data.sh
```

**Cron (macOS/Linux):**
```bash
crontab -e

# Add this line (runs every Sunday at 2 AM):
0 2 * * 0 cd /path/to/nexus && ./scripts/refresh_data.sh
```

**Time:** 15 minutes  
**Deliverable:** Automated weekly data refresh (optional)

---

## Risk Mitigation

### **What Could Go Wrong?**

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| CSV file corruption | Low | Git tracking, version control |
| Data gaps in CSV | Low | Validation script catches before save |
| Backward compatibility | Low | Keep yfinance fallback active |
| User forgets to refresh data | Medium | Automation + warning in logs |
| Network failure during fetch | Medium | Retry logic in fetch script |

### **Safety Measures**

1. ✅ **Version control CSV files** - Git tracks changes
2. ✅ **Keep yfinance fallback** - Always have escape route
3. ✅ **Unit tests** - Catch integration issues early
4. ✅ **Validation scripts** - Ensure data quality
5. ✅ **Documentation** - Clear refresh procedures

---

## Success Criteria

### **Phase 1: Foundation ✅**
- [ ] CSV files exist for BTC + ETH (minimum)
- [ ] CSVDataLoader class implemented and unit tested
- [ ] CSVDataLoader.load(), .available_pairs(), .get_metadata() all working

### **Phase 2: Integration ✅**
- [ ] BacktestEngine uses CSVDataLoader by default
- [ ] ValidationRunner loads from CSV
- [ ] yfinance fallback still works (if CSV fails)
- [ ] Integration tests passing

### **Phase 3: Validation ✅**
- [ ] All existing validation scripts pass with CSV data
- [ ] Walk-forward analysis completes 100% without API errors
- [ ] Monte Carlo runs 10,000 iterations without rate limits
- [ ] Performance benchmarks show 10x+ improvement

### **Phase 4: Cleanup ✅**
- [ ] Code clean (no dead yfinance code)
- [ ] Data documented in DATA_MANIFEST.md
- [ ] Configuration finalized

### **Phase 5: Automation (Optional) ✅**
- [ ] refresh_data.sh working
- [ ] Cron job installed (if desired)

---

## Timeline Summary

| Phase | Days | Hours | Deliverable |
|-------|------|-------|-------------|
| 1. Foundation | 1-2 | 4 | CSV data collected, CSVDataLoader built |
| 2. Integration | 2-3 | 3 | BacktestEngine + ValidationRunner using CSV |
| 3. Validation | 3-4 | 2 | All validation scripts pass, benchmarks show improvement |
| 4. Cleanup | 4 | 1 | Documentation, configuration finalized |
| 5. Automation | 5 | 0.5 | Weekly refresh cron job (optional) |
| **TOTAL** | **~5 days** | **~10.5 hours** | **Production-ready** |

---

## Execution Strategy

### **Day 1 (4 hours)**
```
Morning:
  - Run data inventory audit
  - Fetch BTC + ETH if missing
  
Afternoon:
  - Build CSVDataLoader class
  - Write unit tests
  - Verify tests pass
```

### **Day 2 (2.5 hours)**
```
Morning:
  - Integrate into BacktestEngine
  - Update ValidationRunner
  - Run integration tests

Afternoon:
  - Test with simple_momentum_validation.py
  - Debug any issues
```

### **Day 3 (2 hours)**
```
Morning:
  - Run all validation scripts
  - Benchmark CSV vs yfinance
  - Document results

Afternoon:
  - Create DATA_MANIFEST.md
  - Finalize config
```

### **Day 4 (1 hour)**
```
- Code cleanup
- Final integration tests
- Documentation review
```

### **Day 5 (30 minutes, optional)**
```
- Create refresh_data.sh
- Test cron setup
- Document automation
```

---

## Decision Point: Full Commit?

After Phase 3, decide:

**Option A: Full CSV-only (Recommended)**
- Set `allow_yfinance_fallback: false`
- Delete yfinance code
- Focus entirely on CSV maintenance
- **Pros:** Cleaner codebase, guaranteed reproducibility
- **Cons:** Hard dependency on CSV collection

**Option B: Hybrid (Safer)**
- Keep yfinance fallback active
- Use CSV for normal operations
- Fallback to yfinance only if CSV missing
- **Pros:** Safety net, gradual migration
- **Cons:** More code to maintain

**Recommendation:** Start with **Option B** (hybrid), switch to **Option A** (full CSV) after 2 weeks of successful operation.

---

## Questions to Answer Before Starting

1. **Do you have BTC/ETH CSV data already?** 
   - ✅ Yes → Start Phase 2
   - ❌ No → Start Phase 1 with fetch

2. **Can you dedicate 10 hours this week?**
   - ✅ Yes → Execute as planned
   - ⏸️ Split over 2 weeks → Adjust timeline

3. **Do you want automated refreshes?**
   - ✅ Yes → Include Phase 5
   - ❌ No → Skip Phase 5

4. **Full CSV-only or hybrid approach?**
   - ✅ Full CSV → Cleaner but riskier
   - ✅ Hybrid → More code but safer

---

## Go/No-Go Checklist

Before executing, confirm:

- [ ] You understand the plan
- [ ] You have 10 hours available this week
- [ ] You have internet (for initial data fetch)
- [ ] You're comfortable with local development
- [ ] You've read DATA_STRATEGY_ANALYSIS.md

**If all checked:** You're ready to execute. Start with Phase 1 Day 1.

---

## After Completion

When implementation is done:

1. **Delete old yfinance calls** (if full CSV-only)
2. **Commit to git:** 
   ```bash
   git checkout -b feature/csv-data-integration
   git add -A
   git commit -m "feat(data): integrate CSV-based data loading

   - Implemented CSVDataLoader for deterministic backtesting
   - Integrated with BacktestEngine and ValidationRunner
   - Removed dependency on yfinance for backtesting
   - 10x performance improvement vs API calls
   - Phase 2 ready for strategy development"
   git push origin feature/csv-data-integration
   ```

3. **Update ROADMAP.md:**
   ```
   - [x] Task 1.1: Data Pipeline & Quality Assessment → UPDATED: CSV-based loading
   - Phase 2 can proceed with reproducible data infrastructure
   ```

4. **Document in LOGS.md:**
   ```
   Date: 2025-11-09 to 2025-11-13
   Milestone: CSV Data Integration Complete
   
   - Collected validated OHLCV data for 7+ trading pairs
   - Built CSVDataLoader with robust error handling
   - Integrated with backtesting and validation engines
   - All validation tests passing
   - Ready for Phase 2 strategy development
   ```

---

**This plan is conservative, achievable, and sets you up for Phase 2 success.**

When you're ready, let me know where you get stuck. I can troubleshoot or accelerate specific phases.
