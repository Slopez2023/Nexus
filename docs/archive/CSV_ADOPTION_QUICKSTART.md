# CSV Data Adoption Quickstart

Get pre-validated OHLCV data loaded into NEXUS backtesting within 24 hours.

---

## Step 1: Inventory Current Data (5 minutes)

```bash
# Count what you have
find src/nexus/ohlcv -name "*.csv" -type f | wc -l

# See file sizes
du -sh src/nexus/ohlcv/

# List all available pairs/timeframes
for dir in src/nexus/ohlcv/*/; do
  asset=$(basename "$dir")
  files=$(ls "$dir"/*.csv 2>/dev/null | wc -l)
  echo "$asset: $files files"
done
```

**Expected Output:**
```
BTC: 8 files
ETH: 5 files
SOL: 3 files
... (9+ assets total)
```

---

## Step 2: Fetch Critical Pairs for Phase 2 (1-2 hours)

### **Which pairs to fetch?**

**Minimum (for testing):**
```
BTC-1d-260wks   (BTC 5 years daily)
ETH-1d-260wks   (ETH 5 years daily)
```

**Recommended (for robust strategy):**
```
BTC-1d-260wks   (BTC 5 years daily)
ETH-1d-260wks   (ETH 5 years daily)
SOL-1d-260wks   (SOL 3+ years daily)
AVAX-1d-260wks  (AVAX daily)
BNB-1d-260wks   (BNB daily)
XRP-1d-260wks   (XRP daily)
DOGE-1d-260wks  (DOGE daily)
```

**Extended (for parameter optimization):**
```
# Add 1h timeframe for pairs above (4h data = 52 weeks)
BTC-1h-52wks
ETH-1h-52wks
SOL-1h-52wks
```

### **Fetch Command Template**

```bash
# Single pair
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC \
  --timeframe 1d \
  --weeks 260 \
  --source ccxt-binanceus \
  --strict \
  --overwrite

# Run 5-10 at a time in background
for symbol in BTC ETH SOL AVAX BNB; do
  python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset $symbol \
    --timeframe 1d \
    --weeks 260 \
    --source ccxt-binanceus \
    --strict &
done
wait
```

### **Expected Runtime**
- Single pair, 1 year daily: 30 seconds
- Single pair, 5 years daily: 2-3 minutes
- Parallel (5 pairs): ~10 minutes total

### **What to Look For**

✅ **Success output:**
```
⚙️  CONFIG
  asset: BTC
  timeframe: 1d
  weeks: 260
  sources: ccxt-bitfinex2 → ... → yahoo
  range: [2020-11-09 ... 2025-11-09)
  aligned: [2020-11-09 ... 2025-11-09)

📊 Summary
  status: SUCCESS
  expected: 1826 candles
  received: 1826 candles
  missing: 0
  file: src/nexus/ohlcv/BTC/BTC-1d-260wks-data.csv
  size: 125.3 KB
```

⚠️ **Warning (OK to accept):**
```
⚠️  Data gaps detected: 5.2%
⚠️  Extreme price changes (>50%): 1
```

❌ **Stop if you see:**
```
❌ FAILED
reason: No data returned from all sources
  → Check API keys (BINANCE_API_KEY, KRAKEN_API_KEY in .env)
  → Or use --source yahoo (free, but lower quality)
```

---

## Step 3: Create CSV Data Loader (30 minutes)

Create `src/nexus/core/data_loader.py`:

```python
"""Load pre-validated OHLCV CSV data for backtesting."""

from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
from nexus.core.exceptions import DataError


class CSVDataLoader:
    """Load OHLCV data from CSV storage for reproducible backtests."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize loader with data directory."""
        if data_dir is None:
            data_dir = "src/nexus/ohlcv"
        self.data_dir = Path(data_dir)
        
        if not self.data_dir.exists():
            raise DataError(f"Data directory not found: {self.data_dir}")
    
    def load(self, symbol: str, timeframe: str = "1d") -> pd.DataFrame:
        """
        Load OHLCV data for a symbol/timeframe.
        
        Args:
            symbol: e.g. "BTC", "ETH", "SOL"
            timeframe: e.g. "1m", "5m", "1h", "4h", "1d"
        
        Returns:
            DataFrame with datetime index and OHLCV columns (Open, High, Low, Close, Volume)
        
        Raises:
            DataError: If no data found or loading fails
        """
        symbol_upper = symbol.upper()
        asset_dir = self.data_dir / symbol_upper
        
        if not asset_dir.exists():
            raise DataError(f"No data directory for {symbol_upper}")
        
        # Find matching CSV files
        pattern = f"{symbol_upper}-{timeframe}-*.csv"
        matching_files = list(asset_dir.glob(pattern))
        
        if not matching_files:
            raise DataError(
                f"No CSV files found for {symbol_upper}-{timeframe} in {asset_dir}\n"
                f"Available: {self.available_pairs()}"
            )
        
        # Use most recent file if multiple exist
        csv_file = sorted(matching_files, key=lambda x: x.stat().st_mtime)[-1]
        
        try:
            # Load CSV with datetime parsing
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            
            # Normalize column names
            df.columns = [col.capitalize() for col in df.columns]
            
            # Ensure proper dtypes
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Remove NaN rows
            df = df.dropna()
            
            # Validate OHLC logic (High >= Open,Close >= Low)
            invalid = (df["High"] < df[["Open", "Close"]].max(axis=1)).sum()
            if invalid > 0:
                raise DataError(f"{invalid} rows with invalid OHLC logic")
            
            return df
        
        except Exception as e:
            raise DataError(f"Failed to load {csv_file}: {e}")
    
    def available_pairs(self) -> Dict[str, List[str]]:
        """
        Return available pairs and their timeframes.
        
        Returns:
            {symbol: [timeframes]}
            Example: {"BTC": ["1d", "1h", "4h"], "ETH": ["1d"]}
        """
        pairs = {}
        
        for asset_dir in self.data_dir.iterdir():
            if not asset_dir.is_dir() or asset_dir.name.startswith("."):
                continue
            
            symbol = asset_dir.name.upper()
            timeframes = []
            
            for csv_file in asset_dir.glob("*.csv"):
                # Parse filename: SYMBOL-TIMEFRAME-WEEKS-data.csv
                parts = csv_file.stem.split("-")
                if len(parts) >= 3:
                    timeframe = parts[1]
                    if timeframe not in timeframes:
                        timeframes.append(timeframe)
            
            if timeframes:
                pairs[symbol] = sorted(timeframes)
        
        return pairs
    
    def get_metadata(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Get metadata about a data file (date range, size, etc)."""
        symbol_upper = symbol.upper()
        asset_dir = self.data_dir / symbol_upper
        
        pattern = f"{symbol_upper}-{timeframe}-*.csv"
        matching_files = list(asset_dir.glob(pattern))
        
        if not matching_files:
            return {}
        
        csv_file = sorted(matching_files, key=lambda x: x.stat().st_mtime)[-1]
        df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
        
        return {
            "file": str(csv_file.relative_to(self.data_dir)),
            "size_kb": csv_file.stat().st_size / 1024,
            "rows": len(df),
            "date_start": df.index.min().isoformat(),
            "date_end": df.index.max().isoformat(),
            "date_range_days": (df.index.max() - df.index.min()).days,
        }


# Global instance for easy access
_loader: Optional[CSVDataLoader] = None


def get_csv_loader(data_dir: Optional[str] = None) -> CSVDataLoader:
    """Get or create global CSV loader instance."""
    global _loader
    if _loader is None:
        _loader = CSVDataLoader(data_dir)
    return _loader
```

### **Test the loader (5 minutes)**

```python
# In tests/test_data_loader.py
from nexus.core.data_loader import CSVDataLoader

def test_csv_loader():
    loader = CSVDataLoader("src/nexus/ohlcv")
    
    # Show available data
    pairs = loader.available_pairs()
    print(f"Available pairs: {pairs}")
    
    # Load BTC daily data
    btc_data = loader.load("BTC", "1d")
    print(f"\nBTC 1d data shape: {btc_data.shape}")
    print(f"Date range: {btc_data.index.min()} to {btc_data.index.max()}")
    print(f"\nFirst rows:\n{btc_data.head()}")
    print(f"\nMetadata: {loader.get_metadata('BTC', '1d')}")

if __name__ == "__main__":
    test_csv_loader()
```

```bash
# Run test
python tests/test_data_loader.py
```

---

## Step 4: Integrate with Backtesting Engine (30 minutes)

### **Modify `src/nexus/backtesting/engine.py`**

```python
# At top of file
from nexus.core.data_loader import CSVDataLoader

# In BacktestEngine.__init__:
def __init__(self, config: Optional[Dict[str, Any]] = None):
    self.config = config or {}
    self.data_loader = CSVDataLoader(
        config.get("data_dir", "src/nexus/ohlcv")
    )
    # ... rest of init

# In BacktestEngine.run_backtest:
def run_backtest(
    self,
    strategy_func: Callable,
    symbol: str = "BTC",
    timeframe: str = "1d",
    **kwargs
) -> BacktestResult:
    """Run backtest with CSV data."""
    
    # Load data instead of yfinance
    self.logger.info(f"Loading {symbol} {timeframe} data from CSV...")
    try:
        price_data = self.data_loader.load(symbol, timeframe)
    except Exception as e:
        self.logger.error(f"Failed to load data: {e}")
        raise
    
    # Rest of backtest logic unchanged...
    return self._run_simulation(strategy_func, price_data, **kwargs)
```

### **Update existing strategies**

```python
# In simple_momentum_validation.py, replace:
# price_data = yf.download(...) 

# With:
from nexus.core.data_loader import get_csv_loader
loader = get_csv_loader()
price_data = loader.load("BTC", "1d")
```

---

## Step 5: Verify Integration (30 minutes)

Run existing validation scripts with CSV data:

```bash
# Test with CSV instead of yfinance
python simple_momentum_validation.py

# Expected output:
# ✅ Loading BTC 1d from CSV
# ✅ Generating signals
# ✅ Walking forward with CSV data
# ✅ Monte Carlo simulation complete
# ✅ All validation passed
```

---

## Step 6: Set Up Weekly Data Refresh (10 minutes)

Create `scripts/refresh_data.sh`:

```bash
#!/bin/bash
# Weekly data refresh for Phase 2 pairs

set -e

echo "🔄 Refreshing OHLCV data..."

# Update these pairs weekly
PAIRS=("BTC" "ETH" "SOL" "AVAX" "BNB" "XRP" "DOGE")
TIMEFRAME="1d"
WEEKS=260

for pair in "${PAIRS[@]}"; do
  echo "📥 Fetching $pair-$TIMEFRAME-${WEEKS}wks..."
  python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset "$pair" \
    --timeframe "$TIMEFRAME" \
    --weeks "$WEEKS" \
    --source ccxt-binanceus \
    --strict \
    --overwrite
done

echo "✅ Data refresh complete"
```

### **Schedule with cron (macOS/Linux)**

```bash
# Edit crontab
crontab -e

# Add (runs every Sunday at 2 AM)
0 2 * * 0 /path/to/nexus/scripts/refresh_data.sh >> /path/to/nexus/logs/data_refresh.log 2>&1
```

---

## Troubleshooting

### **"No data found for BTC-1d"**
```bash
# Check what files exist
ls -la src/nexus/ohlcv/BTC/*.csv

# Fetch it
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260 --strict
```

### **"Failed to load CSV: datetime columns have NaT values"**
```bash
# The CSV has missing rows. Options:
# 1. Fetch fresh with gap-refill enabled:
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260 --gap-refill --strict

# 2. Or accept gaps (remove --strict):
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260
```

### **"CCXT not installed" or API key errors**
```bash
# Install CCXT
pip install ccxt

# Set API keys in .env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# Or fall back to free Yahoo Finance (lower quality)
--source yahoo
```

---

## What You'll Have After These Steps

✅ **7-10 trading pairs** with daily OHLCV data (5 years)  
✅ **CSV Data Loader** integrated into backtesting engine  
✅ **Reproducible backtests** (identical data every run)  
✅ **Ready for Phase 2** strategy development  
✅ **Zero API costs** for backtesting  
✅ **Weekly refresh automation** (optional)  

---

## Time Estimate

| Step | Time | Status |
|------|------|--------|
| 1. Inventory | 5 min | Quick |
| 2. Fetch data | 1-2 hrs | One-time |
| 3. Build loader | 30 min | Coding |
| 4. Integrate | 30 min | Coding |
| 5. Verify | 30 min | Testing |
| 6. Automation | 10 min | Optional |
| **Total** | **~3.5 hours** | **Done by tomorrow** |

---

## Next: What to Do with CSV Data

Once loaded, you'll use it for:

1. **Walk-Forward Analysis** - Roll through time windows, optimize on train, test on validation
2. **Monte Carlo Simulation** - 10,000 random resamples to assess statistical robustness
3. **Multi-Regime Testing** - Performance across bull/bear/sideways markets
4. **Parameter Optimization** - Find best values for your strategy

All of this is possible with CSVs loaded. Live APIs would slow you down.

---

*Ready to move fast on Phase 2 without API headaches.*
