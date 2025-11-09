OHLCV Data Catalog

Purpose
- This folder stores local, static market data for backtests. Agents and tools read these CSVs directly (no APIs).

Directory
- Path: `src/data/ohlcv`
- You may add subfolders to organize by asset or timeframe. Files are discovered recursively.

File Naming (approved standard)
- Pattern: `ASSET-CANDLESIZE-TOTALWKS-data.csv`
  - Examples: `BTC-5m-30wks-data.csv`, `ETH-1d-1000wks-data.csv`, `SOL-1h-1000wks-data.csv`
- Filenames are recorded in results as `Data_Source`.

CSV Format (required columns)
- Exact header (lowercase): `datetime,open,high,low,close,volume`
- Datetime can be ISO date or datetime (e.g., `2016-05-18` or `2023-01-01 00:00:00`).
- The loader is case-insensitive and drops unnamed columns, then capitalizes OHLCV for Backtesting.py.
- Notes:
  - Columns are case-normalized internally (lowercased, trimmed).
  - Unnamed columns are ignored/dropped.
  - Datetime is parsed to an index; OHLCV columns are capitalized for Backtesting.py.

Example (minimal)
datetime,open,high,low,close,volume
2016-05-18,12.5,14.93,12.5,13.18,482.52182654
2016-05-19,13.18,14.9,13.0,14.9,950.44120523

Data Source Tracking
- The multi-data tester records the source filename in results under `Data_Source`.
- Results are written next to each executing backtest in `backtests/results/{strategy}.csv`.

Overriding Location
- Default search roots:
  1) Environment variable `LOCAL_DATA_DIR` (if set)
  2) `src/data/ohlcv`
  3) Fallback `src/data/rbi`

Inventory (approved CSVs)

Current files in `src/data/ohlcv`:
- BTC-5m-30wks-data.csv
- BTC-6h-1000wks-data.csv
- ETH-1d-1000wks-data.csv
- ETH-1h-1000wks-data.csv
- SOL-1h-1000wks-data.csv

Notes
- Filenames include asset and timeframe hints (e.g., 5m, 6h, 1h, 1d).
- The loader relies on headers inside each CSV, not the filename; filenames are recorded in results as `Data_Source`.

Adding More Data
- Place additional CSVs in this folder (or subfolders). They will be discovered automatically.
- Keep the same header format described above to ensure compatibility.
