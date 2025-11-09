# CSV Implementation Quick Reference

**Print this. Keep it visible while executing.**

---

## Phase 1: Data Collection (4 hours)

### Step 1: Check what you have
```bash
find src/nexus/ohlcv -name "*.csv" | wc -l
du -sh src/nexus/ohlcv/
```

### Step 2: Fetch missing pairs (BTC + ETH minimum)
```bash
# One at a time
python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset BTC --timeframe 1d --weeks 260 --source ccxt-binanceus --strict

python src/nexus/ohlcv/ohlcv_fetch_validate.py \
  --asset ETH --timeframe 1d --weeks 260 --source ccxt-binanceus --strict

# Or parallel (optional)
for symbol in BTC ETH SOL AVAX BNB; do
  python src/nexus/ohlcv/ohlcv_fetch_validate.py \
    --asset $symbol --timeframe 1d --weeks 260 --source ccxt-binanceus --strict &
done
wait
```

**Expected:** ✅ success, 1800+ candles, 0 missing

### Step 3: Verify data
```bash
python -c "
from nexus.core.data_loader import get_csv_loader
loader = get_csv_loader()
pairs = loader.available_pairs()
print('Available pairs:', pairs)
btc = loader.load('BTC', '1d')
print(f'BTC 1d: {len(btc)} rows, {btc.index.min()} to {btc.index.max()}')
"
```

---

## Phase 2: Code Changes (3 hours)

### Create `src/nexus/core/data_loader.py`

**Copy full code from IMPLEMENTATION_PLAN_CSV.md → "Phase 2.1: Create CSVDataLoader"**

```bash
# After creating file:
pytest tests/core/test_data_loader.py -v
```

**Expected:** ✅ All tests pass

### Update `src/nexus/backtesting/engine.py`

Add at top:
```python
from nexus.core.data_loader import get_csv_loader
```

Add to `__init__`:
```python
self.csv_loader = get_csv_loader(config.get("csv_data_dir", "src/nexus/ohlcv"))
self.use_csv_primary = config.get("use_csv_primary", True)
```

Add new method:
```python
def _get_price_data(self, symbol: str, timeframe: str = "1d", 
                    start_date=None, end_date=None):
    if self.use_csv_primary:
        try:
            return self.csv_loader.load(symbol, timeframe, start_date, end_date)
        except Exception as e:
            self.logger.warning(f"CSV failed: {e}. Using yfinance fallback.")
    
    import yfinance as yf
    return yf.download(symbol, start=start_date, end=end_date)
```

Update `run_backtest()` to call:
```python
price_data = self._get_price_data(symbol, timeframe, start_date, end_date)
```

### Update `config.json`

Add to `backtesting` section:
```json
"use_csv_primary": true,
"csv_data_dir": "src/nexus/ohlcv"
```

### Run integration tests
```bash
pytest tests/backtesting/test_backtest_csv.py -v
```

**Expected:** ✅ Tests pass with CSV data

---

## Phase 3: Validation (2 hours)

### Run existing validation scripts
```bash
python simple_momentum_validation.py
python simple_mean_reversion_validation.py
python simple_rsi_divergence_validation.py
python simple_trend_following_validation.py
```

**Expected:** ✅ All complete successfully with CSV data

### Benchmark improvement
```bash
python scripts/benchmark_data_loading.py
```

**Expected:** CSV 10-50x faster than yfinance

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `No data for BTC` | Run fetch command above |
| `CCXT not installed` | `pip install ccxt` |
| `Import error: data_loader` | File created in `src/nexus/core/`? |
| `Test fails: BTC not found` | Re-run fetch with `--overwrite` |
| `Timestamp parsing error` | Check CSV has `datetime` column |

---

## Success Indicators

✅ **Phase 1 complete when:**
- `ls src/nexus/ohlcv/BTC/*1d*.csv` shows files
- `ls src/nexus/ohlcv/ETH/*1d*.csv` shows files
- Python loader can access them

✅ **Phase 2 complete when:**
- `pytest tests/core/test_data_loader.py -v` passes
- `pytest tests/backtesting/test_backtest_csv.py -v` passes
- BacktestEngine uses CSV by default

✅ **Phase 3 complete when:**
- All 4 validation scripts run with CSV data
- Benchmark shows CSV 10x+ faster
- No yfinance API calls in backtest logs

---

## Files Created/Modified

**New Files:**
- `src/nexus/core/data_loader.py` (300 lines)
- `tests/core/test_data_loader.py` (150 lines)
- `tests/backtesting/test_backtest_csv.py` (100 lines)
- `scripts/benchmark_data_loading.py` (100 lines)

**Modified Files:**
- `src/nexus/backtesting/engine.py` (+40 lines)
- `config.json` (+2 lines)

**Documentation:**
- `docs/DATA_STRATEGY_ANALYSIS.md` ← Already created
- `docs/CSV_ADOPTION_QUICKSTART.md` ← Already created
- `docs/IMPLEMENTATION_PLAN_CSV.md` ← This plan
- `QUICK_START_CSV.md` ← This file

---

## Time Estimates

| Phase | Est. Time | Actual | Status |
|-------|-----------|--------|--------|
| 1. Data Collection | 4 hrs | — | Not started |
| 2. Code Changes | 3 hrs | — | Not started |
| 3. Validation | 2 hrs | — | Not started |
| 4. Documentation | 1 hr | — | Not started |
| **TOTAL** | **10 hrs** | — | — |

---

## Checkpoint: Ready to Start?

Answer these before beginning:

1. Do you have CSV files for BTC + ETH? → `find src/nexus/ohlcv -name "*.csv" | wc -l`
2. Can you run Python scripts? → `python --version`
3. Is CCXT available? → `pip list | grep ccxt`
4. Do you have 10 hours this week? → Schedule it
5. Have you read IMPLEMENTATION_PLAN_CSV.md? → Check ✓

**If all yes:** Start Phase 1 now.

---

## During Execution

**Log your progress:**
```bash
# Track what you've done
# Day 1: Completed Phase 1 (data collection)
# Day 2: Completed Phase 2 (code changes)
# etc.
```

**If stuck:**
1. Check troubleshooting table above
2. Re-read relevant section in IMPLEMENTATION_PLAN_CSV.md
3. Run specific test in isolation
4. Review error messages carefully (usually self-explanatory)

---

## After Completion

```bash
# Commit to git
git checkout -b feature/csv-data-integration
git add -A
git commit -m "feat(data): integrate CSV-based data loading

- Implemented CSVDataLoader for deterministic backtesting
- Integrated with BacktestEngine and ValidationRunner
- 10x performance improvement vs yfinance
- Phase 2 ready"
git push origin feature/csv-data-integration

# Create pull request / merge to main
```

---

**You've got this. The plan is solid. Start Phase 1 today.**
