#!/usr/bin/env python3
"""
OHLCV Fetch + Validate + Save

Configure parameters in CONFIG (or via CLI args). The script:
- Fetches OHLCV data from a selected source (default: yfinance crypto USD).
- Normalizes to the required schema: datetime,open,high,low,close,volume
- Validates strict data quality (10 rules).
- Saves CSV to src/data/ohlcv (or LOCAL_DATA_DIR if set) using filename pattern:
  ASSET-CANDLESIZE-TOTALWKS-data.csv

Dependencies:
  pip install pandas numpy yfinance pytz
Optional (extra sources):
  pip install ccxt

Examples:
  python src/data/ohlcv/ohlcv_fetch_validate.py --asset BTC --timeframe 6h --weeks 1000 --source yahoo --strict
  python src/data/ohlcv/ohlcv_fetch_validate.py --asset ETH --timeframe 1h --start 2018-01-01 --end 2024-01-01 --source yahoo --strict
  LOCAL_DATA_DIR=/custom/dir python src/data/ohlcv/ohlcv_fetch_validate.py --asset SOL --timeframe 1d --weeks 520
  # CCXT Binance (optional API keys BINANCE_API_KEY/SECRET)
  python src/data/ohlcv/ohlcv_fetch_validate.py --asset BTC --timeframe 6h --weeks 260 --source ccxt-binance --strict
  # CCXT Kraken (optional API keys KRAKEN_API_KEY/SECRET)
  python src/data/ohlcv/ohlcv_fetch_validate.py --asset BTC --timeframe 6h --weeks 260 --source ccxt-kraken --strict

Notes:
- For long ranges at sub-daily granularity, the script chunk-fetches data to avoid provider limits.
- Exchange-specific data via CCXT supported: binance, binanceus, kraken, bitfinex(2), coinbase, okx, bybit, kucoin, bitstamp, gateio. Use --source or --sources to set order. Optional API keys via env (see .env.example).
"""

from __future__ import annotations
import os
import sys
import math
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd

try:
    import yfinance as yf  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    yf = None  # yfinance may be optional if only ccxt is used

# ccxt is optional; import lazily when used
ccxt = None  # loaded on demand


# =========================
# Config (edit these or use CLI)
# =========================

@dataclass
class Config:
    # Asset symbol (e.g., "BTC", "ETH", "SOL")
    asset: str = "BTC"

    # Canonical timeframe string ("5m","15m","1h","4h","6h","1d")
    timeframe: str = "15m"

    # Total weeks to collect (for file naming & expected coverage)
    total_weeks: int = 200

    # Date range (UTC). If None, derive from total_weeks ending now.
    start_utc: Optional[str] = None   # e.g., "2015-01-01"
    end_utc: Optional[str] = None     # e.g., "2025-01-01"

    # Data source choice: "yahoo" (yfinance), "ccxt-binance", "ccxt-binanceus",
    # "ccxt-kraken", "ccxt-bitfinex2", or "ccxt-coinbase"
    source: str = "ccxt-binanceus"
    # Prioritized fallback chain; missing/invalid candles will be filled from
    # these sources in order. Smart default order aims for deepest minute/hour
    # coverage and broad availability; you usually don't need to set --source.
    # Default: Bitfinex → OKX → Bybit → BinanceUS → Kraken → KuCoin → Coinbase → Gate.io → Bitstamp → Binance → Yahoo
    sources: List[str] = field(default_factory=lambda: [
        "ccxt-bitfinex2", "ccxt-okx", "ccxt-bybit", "ccxt-binanceus",
        "ccxt-kraken", "ccxt-kucoin", "ccxt-coinbase", "ccxt-gateio",
        "ccxt-bitstamp", "ccxt-binance", "yahoo"
    ])

    # Destination directory. If env var LOCAL_DATA_DIR is set, it overrides this.
    output_dir: str = "src/data/ohlcv"

    # Strict mode: fail on any validation issue
    strict: bool = True

    # Outlier threshold (deprecated: now uses adaptive rolling volatility 3σ bands)
    # Kept for backwards compatibility but no longer used in validation
    outlier_threshold: float = 0.30

    # Exchange sanity check bounds for BTC (approx historical ranges)
    btc_min_usd: float = 0.5
    btc_max_usd: float = 200000.0

    # Enforce timestamps represent end-of-window closes
    enforce_window_close: bool = True

    # Overwrite existing output file if present
    overwrite: bool = False

    # Print missing timestamps after fetch if gaps remain
    print_missing: bool = False
    # Attempt a targeted gap-refill pass for remaining missing candles
    gap_refill: bool = False
    # Optional path to write a missing-timestamps report
    missing_report: Optional[str] = None

    # Nesting strategy for output directory: one of 'flat', 'asset', 'timeframe', 'asset-timeframe'
    nest: str = "asset"


CONFIG = Config()


# =========================
# Helpers
# =========================

# ---------- Pretty console output (colors + emojis) ----------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

E_CFG = "⚙️"
E_FETCH = "📥"
E_INFO = "ℹ️"
E_VALIDATE = "🧪"
E_OK = "✅"
E_ERR = "❌"
E_WARN = "⚠️"
E_SAVE = "💾"
E_SUM = "📊"
E_HINT = "💡"

def _c(s: str, color: str) -> str:
    return f"{color}{s}{RESET}"

def _kv(k: str, v: str) -> str:
    return f"{_c(k, BOLD)} {_c(v, FG_CYAN)}"

def _human_bytes(n: int) -> str:
    units = ["B","KB","MB","GB","TB"]
    x = float(n)
    for u in units:
        if x < 1024.0:
            return f"{x:.1f} {u}"
        x /= 1024.0
    return f"{x:.1f} PB"

def _ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")

def log_config(cfg: Config, start_dt: datetime, end_dt: datetime, start_aligned: datetime, end_exclusive: datetime) -> None:
    print(_c(f"{E_CFG} CONFIG", FG_MAGENTA))
    print("  " + _kv("asset:", cfg.asset.upper()))
    print("  " + _kv("timeframe:", cfg.timeframe))
    print("  " + _kv("weeks:", str(cfg.total_weeks)))
    # Show chain if configured
    if getattr(cfg, "sources", None):
        chain = " → ".join(cfg.sources)
        print("  " + _kv("sources:", chain))
    else:
        print("  " + _kv("source:", cfg.source))
    print("  " + _kv("range:", f"[{start_dt.isoformat()} .. {end_dt.isoformat()})"))
    print("  " + _kv("aligned:", f"[{start_aligned.isoformat()} .. {end_exclusive.isoformat()})"))

def log_step(msg: str) -> None:
    print(_c(f"{E_FETCH} {msg}", FG_BLUE))

def log_info(msg: str) -> None:
    print(_c(f"{E_INFO} {msg}", FG_CYAN))

def log_warn(msg: str) -> None:
    print(_c(f"{E_WARN} {msg}", FG_YELLOW))

def log_error(msg: str) -> None:
    print(_c(f"{E_ERR} {msg}", FG_RED))

def log_ok(msg: str) -> None:
    print(_c(f"{E_OK} {msg}", FG_GREEN))

def log_hint(msg: str) -> None:
    print(_c(f"{E_HINT} {msg}", FG_YELLOW))

def log_issues(issues: List[str]) -> None:
    for m in issues:
        print(_c(f"   • {m}", FG_RED))

def print_summary(success: bool, *, cfg: Config, start_aligned: datetime, end_exclusive: datetime, got_rows: int, exp_rows: int, out_path: Optional[str] = None, df_first: Optional[datetime] = None, df_last: Optional[datetime] = None, reason: Optional[str] = None, status_text: Optional[str] = None, status_color: str = FG_GREEN) -> None:
    print(_c(f"\n{E_SUM} Summary", FG_MAGENTA))
    if status_text:
        status = _c(status_text, status_color)
    else:
        status = _c("SUCCESS", FG_GREEN) if success else _c("FAILED", FG_RED)
    print("  " + _kv("status:", status))
    print("  " + _kv("asset:", cfg.asset.upper()))
    print("  " + _kv("timeframe:", cfg.timeframe))
    # Print chain if available
    if getattr(cfg, "sources", None):
        print("  " + _kv("sources:", " → ".join(cfg.sources)))
    else:
        print("  " + _kv("source:", cfg.source))
    print("  " + _kv("aligned:", f"[{start_aligned.isoformat()} .. {end_exclusive.isoformat()})"))
    print("  " + _kv("expected:", f"{exp_rows} candles"))
    print("  " + _kv("received:", f"{got_rows} candles"))
    miss = max(exp_rows - got_rows, 0)
    print("  " + _kv("missing:", f"{miss}"))
    if df_first is not None and df_last is not None:
        print("  " + _kv("first:", df_first.isoformat()))
        print("  " + _kv("last:", df_last.isoformat()))
    if out_path:
        try:
            size = os.path.getsize(out_path)
            print("  " + _kv("file:", out_path))
            print("  " + _kv("size:", _human_bytes(size)))
        except Exception:
            print("  " + _kv("file:", out_path))
    if reason:
        print("  " + _kv("reason:", reason))

TF_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
}


def week_candles(timeframe: str) -> int:
    s = TF_TO_SECONDS[timeframe]
    return int(round(7 * 86400 / s))


def _rolling_window_for_timeframe(timeframe: str) -> int:
    """
    Compute rolling window size for volatility calculation based on timeframe.
    Aims for ~30 days of data (appropriate for outlier detection across regimes).
    """
    s = TF_TO_SECONDS[timeframe]
    candles_per_day = 86400 / s
    return max(20, int(30 * candles_per_day))  # At least 20, typically 30 days


def to_tz_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso_utc(s: str) -> datetime:
    return to_tz_aware_utc(pd.to_datetime(s, utc=True).to_pydatetime())


def derive_range_from_weeks(total_weeks: int, end_utc: Optional[str]) -> Tuple[datetime, datetime]:
    end_dt = parse_iso_utc(end_utc) if end_utc else datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(weeks=total_weeks)
    return start_dt, end_dt


def floor_to_boundary(ts: datetime, timeframe: str) -> datetime:
    s = TF_TO_SECONDS[timeframe]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    n = int((ts - epoch).total_seconds())
    floored = (n // s) * s
    return epoch + timedelta(seconds=floored)


def ceil_to_boundary(ts: datetime, timeframe: str) -> datetime:
    s = TF_TO_SECONDS[timeframe]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    n = int((ts - epoch).total_seconds())
    ceiled = ((n + s - 1) // s) * s
    return epoch + timedelta(seconds=ceiled)


def align_bounds_half_open(start_dt: datetime, end_dt: datetime, timeframe: str) -> Tuple[datetime, datetime]:
    """
    Aligns bounds for half-open range [start_aligned, end_exclusive) using candle close timestamps.
    - start_aligned: first included close time (ceil to next boundary)
    - end_exclusive: first boundary strictly after end_dt (ceil to next boundary)
    Use trimming: index >= start_aligned and index < end_exclusive
    """
    start_aligned = ceil_to_boundary(start_dt, timeframe)
    end_exclusive = ceil_to_boundary(end_dt, timeframe)
    return start_aligned, end_exclusive


def expected_count_half_open(start_aligned: datetime, end_exclusive: datetime, timeframe: str) -> int:
    s = TF_TO_SECONDS[timeframe]
    delta = (end_exclusive - start_aligned).total_seconds()
    if delta <= 0:
        return 0
    return int(delta // s)


def align_to_window_close(index: pd.DatetimeIndex, timeframe: str) -> pd.DatetimeIndex:
    s = TF_TO_SECONDS[timeframe]
    # Round down each timestamp to its boundary (end-of-window close)
    # We treat close times as exact multiples of s since epoch (UTC)
    epoch_seconds = 0
    idx_seconds = (index.view("int64") // 10**9).astype(np.int64)
    aligned = ((idx_seconds // s) * s) + epoch_seconds
    return pd.to_datetime(aligned, unit="s", utc=True)


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Lowercase and remove any unwanted columns
    df.columns = [str(c).lower().strip() for c in df.columns]
    # Drop adjusted close if present
    if "adj close" in df.columns:
        df = df.drop(columns=["adj close"])
    keep = ["open", "high", "low", "close", "volume"]
    # some sources may provide these exact names; reindex to ensure order
    df = df.reindex(columns=keep)
    # Ensure floats
    for c in keep:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def resample_to_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample OHLCV to the requested timeframe with right-labeled (end-of-window) timestamps.
    """
    rule = timeframe.upper().replace("H", "H").replace("M", "T")
    # Pandas expects offsets like '6H', '5min', '1D'
    if timeframe.endswith("m"):
        rule = f"{int(TF_TO_SECONDS[timeframe]//60)}min"
    elif timeframe.endswith("h"):
        rule = f"{int(TF_TO_SECONDS[timeframe]//3600)}H"
    elif timeframe.endswith("d"):
        rule = f"{int(TF_TO_SECONDS[timeframe]//86400)}D"
    else:
        raise ValueError(f"Unsupported timeframe for resample: {timeframe}")

    o = df["open"].resample(rule, label="right", closed="right").first()
    h = df["high"].resample(rule, label="right", closed="right").max()
    l = df["low"].resample(rule, label="right", closed="right").min()
    c = df["close"].resample(rule, label="right", closed="right").last()
    v = df["volume"].resample(rule, label="right", closed="right").sum()
    out = pd.concat([o, h, l, c, v], axis=1)
    out.columns = ["open", "high", "low", "close", "volume"]
    # drop rows where any component missing
    out = out.dropna(how="any")
    return out


# =========================
# Data sources
# =========================

def tf_to_pandas_offset(timeframe: str) -> str:
    if timeframe.endswith("m"):
        return f"{int(TF_TO_SECONDS[timeframe]//60)}min"
    if timeframe.endswith("h"):
        return f"{int(TF_TO_SECONDS[timeframe]//3600)}H"
    if timeframe.endswith("d"):
        return f"{int(TF_TO_SECONDS[timeframe]//86400)}D"
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def expected_index(start_aligned: datetime, end_exclusive: datetime, timeframe: str) -> pd.DatetimeIndex:
    periods = expected_count_half_open(start_aligned, end_exclusive, timeframe)
    if periods <= 0:
        return pd.DatetimeIndex([], tz="UTC")
    freq = tf_to_pandas_offset(timeframe)
    return pd.date_range(start=start_aligned, periods=periods, freq=freq, tz="UTC")

def pick_yfinance_ticker(asset: str) -> str:
    # Most crypto are available via "ASSET-USD"
    return f"{asset.upper()}-USD"


def yfinance_supported_interval(timeframe: str) -> Optional[str]:
    """
    Map requested timeframe to a yfinance interval. If not native, return a finer interval to resample from.
    """
    native = {
        "1m": "1m",
        "2m": "2m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "90m": "90m",  # not used here
        "1d": "1d",
        "5d": "5d",
        "1wk": "1wk",
        "1mo": "1mo",
        "3mo": "3mo",
    }
    # Prefer native when available
    if timeframe in ("1m", "5m", "15m", "30m", "1h", "1d"):
        return timeframe
    # For 2h/4h/6h/8h/12h use 1h then resample
    if timeframe in ("2h", "4h", "6h", "8h", "12h"):
        return "1h"
    return None


def yfinance_chunk_span_days(interval: str) -> int:
    """
    Conservative chunk sizes to avoid provider limits.
    """
    if interval in ("1m", "2m", "5m", "15m", "30m"):
        return 60  # ~2 months
    if interval in ("1h",):
        return 730  # 2 years
    if interval in ("1d",):
        return 3650  # 10 years
    return 365  # default fallback 1 year


def fetch_yfinance(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. pip install yfinance")

    ticker = pick_yfinance_ticker(asset)
    interval = yfinance_supported_interval(timeframe)
    if interval is None:
        raise ValueError(f"Timeframe not supported via yfinance: {timeframe}")

    # Chunked download to bypass interval span limits
    span_days = yfinance_chunk_span_days(interval)
    cur_start = start_dt
    frames: List[pd.DataFrame] = []
    while cur_start < end_dt:
        cur_end = min(cur_start + timedelta(days=span_days), end_dt)
        df = yf.download(
            tickers=ticker,
            interval=interval,
            start=cur_start,
            end=cur_end,
            progress=False,
            auto_adjust=False,
        )
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index, utc=True)
            frames.append(df)
        cur_start = cur_end
        # small pause to be gentle
        time.sleep(0.1)

    if not frames:
        raise RuntimeError("No data retrieved from yfinance.")

    df_all = pd.concat(frames).sort_index()
    # Deduplicate index in case of overlap
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    df_all = normalize_ohlcv(df_all)

    # If requested timeframe differs from download interval, resample
    if interval != timeframe:
        df_all = resample_to_timeframe(df_all, timeframe)

    return df_all


def ensure_ccxt():  # lazy loader
    global ccxt
    if ccxt is None:
        try:
            import ccxt  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("ccxt is not installed. pip install ccxt") from e
        globals()["ccxt"] = ccxt
    return ccxt


def fetch_ccxt_binance(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("BINANCE_API_KEY"),
            "secret": os.environ.get("BINANCE_API_SECRET"),
        })
    exchange = ccxt_mod.binance(params)
    symbol = f"{asset.upper()}/USDT"
    tf = timeframe
    supported = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
    needs_resample = False
    if tf not in supported:
        tf = "1h"
        needs_resample = True

    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 1000  # max per request
    frames: List[pd.DataFrame] = []

    # Fetch sequentially in chunks
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        # advance since by the last timestamp + 1 interval
        last_ts = int(df.index[-1].timestamp() * 1000)
        step_ms = TF_TO_SECONDS[tf] * 1000
        since_ms = last_ts + step_ms
        # respect rate limit
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))

    if not frames:
        raise RuntimeError("No data retrieved from ccxt/binance.")

    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def _select_symbol(exchange, asset: str) -> str:
    """
    Try to find a good symbol for the given asset on an exchange, preferring USDT then USD.
    """
    exchange.load_markets()
    sym = None
    candidates = [f"{asset.upper()}/USDT", f"{asset.upper()}/USD"]
    # handle BTC/XBT edge
    if asset.upper() == "BTC":
        candidates = [f"BTC/USDT", f"BTC/USD", f"XBT/USDT", f"XBT/USD"] + candidates
    for s in candidates:
        if s in exchange.markets:
            sym = s
            break
    if sym is None:
        # scan markets
        for m in exchange.markets.values():
            base = m.get("base")
            quote = m.get("quote")
            if base in (asset.upper(), "XBT" if asset.upper()=="BTC" else None) and quote in ("USDT","USD"):
                sym = m.get("symbol")
                break
    if sym is None:
        raise RuntimeError(f"Symbol for {asset} not found on {exchange.id}")
    return sym


def _pick_exchange_tf(exchange, requested: str) -> tuple[str, bool]:
    """
    Choose the best fetch timeframe supported by an exchange. Returns (fetch_tf, needs_resample).
    """
    tfs = getattr(exchange, "timeframes", None)
    if isinstance(tfs, dict) and requested in tfs:
        return requested, False
    # Fallback: prefer 1m for minute multiples, else 1h
    if requested.endswith("m"):
        base = "1m" if (isinstance(tfs, dict) and "1m" in tfs) else "1m"
        return base, requested != base
    base = "1h"
    return base, requested != base


def _fetch_ccxt_range(exchange, symbol: str, fetch_tf: str, start_dt: datetime, end_dt: datetime, limit: int = 1000) -> List[pd.DataFrame]:
    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    frames: List[pd.DataFrame] = []
    step_ms = TF_TO_SECONDS.get(fetch_tf, TF_TO_SECONDS.get("1h", 3600)) * 1000
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=fetch_tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        last_ts_ms = int(df.index[-1].timestamp() * 1000)
        if last_ts_ms <= since_ms:
            since_ms += step_ms
        else:
            since_ms = last_ts_ms + step_ms
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))
    return frames


def fetch_ccxt_okx(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    # okx uses passphrase
    if os.getenv("OKX_API_KEY") and os.getenv("OKX_API_SECRET") and os.getenv("OKX_API_PASSPHRASE"):
        params.update({
            "apiKey": os.environ.get("OKX_API_KEY"),
            "secret": os.environ.get("OKX_API_SECRET"),
            "password": os.environ.get("OKX_API_PASSPHRASE"),
        })
    exchange = ccxt_mod.okx(params)
    symbol = _select_symbol(exchange, asset)
    fetch_tf, needs_resample = _pick_exchange_tf(exchange, timeframe)
    frames = _fetch_ccxt_range(exchange, symbol, fetch_tf, start_dt, end_dt, limit=100)
    if not frames:
        raise RuntimeError("No data retrieved from ccxt/okx.")
    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_bybit(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("BYBIT_API_KEY") and os.getenv("BYBIT_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("BYBIT_API_KEY"),
            "secret": os.environ.get("BYBIT_API_SECRET"),
        })
    exchange = ccxt_mod.bybit(params)
    symbol = _select_symbol(exchange, asset)
    fetch_tf, needs_resample = _pick_exchange_tf(exchange, timeframe)
    frames = _fetch_ccxt_range(exchange, symbol, fetch_tf, start_dt, end_dt, limit=1000)
    if not frames:
        raise RuntimeError("No data retrieved from ccxt/bybit.")
    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_kucoin(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("KUCOIN_API_KEY") and os.getenv("KUCOIN_API_SECRET") and os.getenv("KUCOIN_API_PASSPHRASE"):
        params.update({
            "apiKey": os.environ.get("KUCOIN_API_KEY"),
            "secret": os.environ.get("KUCOIN_API_SECRET"),
            "password": os.environ.get("KUCOIN_API_PASSPHRASE"),
        })
    exchange = ccxt_mod.kucoin(params)
    symbol = _select_symbol(exchange, asset)
    fetch_tf, needs_resample = _pick_exchange_tf(exchange, timeframe)
    frames = _fetch_ccxt_range(exchange, symbol, fetch_tf, start_dt, end_dt, limit=1000)
    if not frames:
        raise RuntimeError("No data retrieved from ccxt/kucoin.")
    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_bitstamp(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("BITSTAMP_API_KEY") and os.getenv("BITSTAMP_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("BITSTAMP_API_KEY"),
            "secret": os.environ.get("BITSTAMP_API_SECRET"),
        })
    exchange = ccxt_mod.bitstamp(params)
    symbol = _select_symbol(exchange, asset)
    fetch_tf, needs_resample = _pick_exchange_tf(exchange, timeframe)
    frames = _fetch_ccxt_range(exchange, symbol, fetch_tf, start_dt, end_dt, limit=1000)
    if not frames:
        raise RuntimeError("No data retrieved from ccxt/bitstamp.")
    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_gateio(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("GATEIO_API_KEY") and os.getenv("GATEIO_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("GATEIO_API_KEY"),
            "secret": os.environ.get("GATEIO_API_SECRET"),
        })
    exchange = ccxt_mod.gateio(params)
    symbol = _select_symbol(exchange, asset)
    fetch_tf, needs_resample = _pick_exchange_tf(exchange, timeframe)
    frames = _fetch_ccxt_range(exchange, symbol, fetch_tf, start_dt, end_dt, limit=1000)
    if not frames:
        raise RuntimeError("No data retrieved from ccxt/gateio.")
    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_binanceus(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("BINANCEUS_API_KEY") and os.getenv("BINANCEUS_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("BINANCEUS_API_KEY"),
            "secret": os.environ.get("BINANCEUS_API_SECRET"),
        })
    exchange = ccxt_mod.binanceus(params)
    exchange.load_markets()
    symbol = None
    for sym in (f"{asset.upper()}/USDT", f"{asset.upper()}/USD"):
        if sym in exchange.markets:
            symbol = sym
            break
    if symbol is None:
        raise RuntimeError(f"Symbol for {asset} not found on binanceus")

    supported = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
    tf = timeframe
    needs_resample = False
    if tf not in supported:
        tf = "1h"
        needs_resample = True

    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 1000
    frames: List[pd.DataFrame] = []
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        last_ts_ms = int(df.index[-1].timestamp() * 1000)
        step_ms = TF_TO_SECONDS[tf] * 1000
        if last_ts_ms <= since_ms:
            since_ms += step_ms
        else:
            since_ms = last_ts_ms + step_ms
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))

    if not frames:
        raise RuntimeError("No data retrieved from ccxt/binanceus.")

    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_bitfinex2(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("BITFINEX_API_KEY") and os.getenv("BITFINEX_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("BITFINEX_API_KEY"),
            "secret": os.environ.get("BITFINEX_API_SECRET"),
        })
    # Some ccxt builds expose 'bitfinex2', others only 'bitfinex'. Try both.
    if hasattr(ccxt_mod, "bitfinex2"):
        exchange_ctor = getattr(ccxt_mod, "bitfinex2")
    elif hasattr(ccxt_mod, "bitfinex"):
        exchange_ctor = getattr(ccxt_mod, "bitfinex")
    else:
        raise RuntimeError("Bitfinex exchange not available in this ccxt build")
    exchange = exchange_ctor(params)
    exchange.load_markets()
    symbol = None
    for sym in (f"{asset.upper()}/USD", f"{asset.upper()}/USDT"):
        if sym in exchange.markets:
            symbol = sym
            break
    if symbol is None:
        raise RuntimeError(f"Symbol for {asset} not found on bitfinex2")

    supported = {"1m", "5m", "15m", "30m", "1h", "3h", "6h", "12h", "1d"}
    tf = timeframe
    needs_resample = False
    if tf not in supported:
        tf = "1h"
        needs_resample = True

    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 10000
    frames: List[pd.DataFrame] = []
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        last_ts_ms = int(df.index[-1].timestamp() * 1000)
        step_ms = TF_TO_SECONDS[tf] * 1000
        if last_ts_ms <= since_ms:
            since_ms += step_ms
        else:
            since_ms = last_ts_ms + step_ms
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))

    if not frames:
        raise RuntimeError("No data retrieved from ccxt/bitfinex2.")

    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_kraken(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("KRAKEN_API_KEY") and os.getenv("KRAKEN_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("KRAKEN_API_KEY"),
            "secret": os.environ.get("KRAKEN_API_SECRET"),
        })
    exchange = ccxt_mod.kraken(params)
    # Kraken prefers USD (not USDT). BTC base may be XBT internally; CCXT maps BTC/USD in markets too.
    exchange.load_markets()
    symbol = None
    candidates = [f"{asset.upper()}/USD", f"{asset.upper()}/USDT"]
    if asset.upper() == "BTC":
        candidates.insert(0, "BTC/USD")
        candidates.append("XBT/USD")
    for sym in candidates:
        if sym in exchange.markets:
            symbol = sym
            break
    if symbol is None:
        raise RuntimeError(f"Symbol for {asset} not found on Kraken")

    supported = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "7d", "15d"}
    tf = timeframe
    needs_resample = False
    if tf not in supported:
        tf = "1h"
        needs_resample = True

    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 1000
    frames: List[pd.DataFrame] = []
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        last_ts = int(df.index[-1].timestamp() * 1000)
        step_ms = TF_TO_SECONDS[tf] * 1000
        since_ms = last_ts + step_ms
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))

    if not frames:
        raise RuntimeError("No data retrieved from ccxt/kraken.")

    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ccxt_coinbase(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    ccxt_mod = ensure_ccxt()
    params = {"enableRateLimit": True}
    if os.getenv("COINBASE_API_KEY") and os.getenv("COINBASE_API_SECRET"):
        params.update({
            "apiKey": os.environ.get("COINBASE_API_KEY"),
            "secret": os.environ.get("COINBASE_API_SECRET"),
        })
    exchange = ccxt_mod.coinbase(params)
    exchange.load_markets()
    symbol = None
    for sym in (f"{asset.upper()}/USD", f"{asset.upper()}/USDT"):
        if sym in exchange.markets:
            symbol = sym
            break
    if symbol is None:
        raise RuntimeError(f"Symbol for {asset} not found on coinbase")

    # Coinbase Advanced typically supports: 1m,5m,15m,1h,6h,1d
    supported = {"1m", "5m", "15m", "1h", "6h", "1d"}
    tf = timeframe
    needs_resample = False
    if tf not in supported:
        tf = "1h"
        needs_resample = True

    since_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 1000
    frames: List[pd.DataFrame] = []
    while since_ms < end_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, since=since_ms, limit=limit)
        if not ohlcv:
            break
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"]).set_index("datetime").sort_index()
        df = normalize_ohlcv(df)
        frames.append(df)
        last_ts_ms = int(df.index[-1].timestamp() * 1000)
        step_ms = TF_TO_SECONDS[tf] * 1000
        if last_ts_ms <= since_ms:
            since_ms += step_ms
        else:
            since_ms = last_ts_ms + step_ms
        time.sleep((getattr(exchange, "rateLimit", 200) / 1000.0))

    if not frames:
        raise RuntimeError("No data retrieved from ccxt/coinbase.")

    df_all = pd.concat(frames).sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    if needs_resample:
        df_all = resample_to_timeframe(df_all, timeframe)
    return df_all


def fetch_ohlcv(asset: str, timeframe: str, start_dt: datetime, end_dt: datetime, source: str) -> pd.DataFrame:
    if source == "yahoo":
        df = fetch_yfinance(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-binance":
        df = fetch_ccxt_binance(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-binanceus":
        df = fetch_ccxt_binanceus(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-kraken":
        df = fetch_ccxt_kraken(asset, timeframe, start_dt, end_dt)
    elif source in ("ccxt-bitfinex2", "ccxt-bitfinex"):
        df = fetch_ccxt_bitfinex2(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-coinbase":
        df = fetch_ccxt_coinbase(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-okx":
        df = fetch_ccxt_okx(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-bybit":
        df = fetch_ccxt_bybit(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-kucoin":
        df = fetch_ccxt_kucoin(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-bitstamp":
        df = fetch_ccxt_bitstamp(asset, timeframe, start_dt, end_dt)
    elif source == "ccxt-gateio":
        df = fetch_ccxt_gateio(asset, timeframe, start_dt, end_dt)
    else:
        raise ValueError(f"Unsupported source: {source}")

    # Ensure tz-aware UTC index
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()

    # Align timestamps to exact window closes
    aligned_index = align_to_window_close(df.index, timeframe)
    df.index = aligned_index
    df = df[~df.index.duplicated(keep="last")]
    return df


def is_row_complete(df: pd.DataFrame) -> pd.Series:
    """
    Row-level quality gate used during multi-source filling. This is a subset of full validation
    (no outlier/spacing checks), intended to identify missing/invalid candles to be replaced.
    """
    required = ["open", "high", "low", "close", "volume"]
    non_null = ~df[required].isnull().any(axis=1)
    vol_pos = df["volume"] > 0
    candle_logic = (df["low"] <= df["open"]) & (df["open"] <= df["high"]) & (df["low"] <= df["close"]) & (df["close"] <= df["high"])
    return non_null & vol_pos & candle_logic


def fetch_with_fallbacks(asset: str, timeframe: str, start_aligned: datetime, end_exclusive: datetime, sources: List[str]) -> tuple[pd.DataFrame, dict]:
    """
    Fetch from primary source; fill missing/invalid candles from fallbacks in order.
    Returns (combined_df, stats) where stats has per-source fill counts.
    """
    exp_idx = expected_index(start_aligned, end_exclusive, timeframe)
    cols = ["open", "high", "low", "close", "volume"]
    combined = pd.DataFrame(index=exp_idx, columns=cols, dtype="float64")
    fill_stats = {s: 0 for s in sources}

    first_success = False
    for i, src in enumerate(sources):
        try:
            df = fetch_ohlcv(asset, timeframe, start_aligned, end_exclusive, src)
        except Exception as e:
            log_warn(f"{src}: fetch failed ({e}) — skipping")
            continue
        # Trim to half-open window and align to expected index
        df = df[(df.index >= start_aligned) & (df.index < end_exclusive)]
        df = df.reindex(exp_idx)
        valid_mask = is_row_complete(df)

        if not first_success:
            # Seed combined with whatever valid rows we have
            combined.loc[valid_mask, cols] = df.loc[valid_mask, cols]
            missing_after = (~is_row_complete(combined)).sum()
            log_info(f"{src}: seeded {valid_mask.sum()} candles • remaining gaps: {int(missing_after)}")
            first_success = True
        else:
            # Fill only rows that are missing or invalid in combined
            need_mask = ~is_row_complete(combined)
            use_mask = need_mask & valid_mask
            filled = int(use_mask.sum())
            if filled > 0:
                combined.loc[use_mask, cols] = df.loc[use_mask, cols]
            fill_stats[src] += filled
            remaining = int((~is_row_complete(combined)).sum())
            log_info(f"{src}: filled {filled} candles • remaining gaps: {remaining}")

        # Early exit if complete
        if is_row_complete(combined).all():
            break

    # Report if still missing
    remaining = int((~is_row_complete(combined)).sum())
    if remaining > 0:
        log_warn(f"Incomplete after fallbacks — remaining gaps: {remaining}")

    return combined, fill_stats


def _group_missing_runs(missing_idx: pd.DatetimeIndex, timeframe: str) -> List[tuple[pd.Timestamp, pd.Timestamp]]:
    if len(missing_idx) == 0:
        return []
    s = TF_TO_SECONDS[timeframe]
    runs = []
    run_start = missing_idx[0]
    prev = missing_idx[0]
    for ts in missing_idx[1:]:
        if int((ts.to_datetime64().astype('datetime64[s]').astype(int) - prev.to_datetime64().astype('datetime64[s]').astype(int))) == s:
            prev = ts
            continue
        runs.append((run_start, prev))
        run_start = ts
        prev = ts
    runs.append((run_start, prev))
    return runs


def targeted_gap_refill(asset: str, timeframe: str, combined: pd.DataFrame, sources: List[str]) -> tuple[pd.DataFrame, dict]:
    """
    For remaining missing timestamps, try fetching small windows around each gap from sources in order.
    Returns (updated_df, refill_stats).
    """
    cols = ["open", "high", "low", "close", "volume"]
    missing_mask = ~is_row_complete(combined)
    missing_idx = combined.index[missing_mask]
    runs = _group_missing_runs(missing_idx, timeframe)
    s = TF_TO_SECONDS[timeframe]
    refill_stats = {sname: 0 for sname in sources}
    for src in sources:
        if len(runs) == 0:
            break
        new_runs = []
        filled_total = 0
        for (start_ts, end_ts) in runs:
            # Expand a little to be safe
            fetch_start = start_ts - timedelta(seconds=s)
            fetch_end = end_ts + timedelta(seconds=s)
            try:
                df = fetch_ohlcv(asset, timeframe, fetch_start, fetch_end, src)
            except Exception:
                # keep this run for next source
                new_runs.append((start_ts, end_ts))
                continue
            df = df[(df.index >= fetch_start) & (df.index <= fetch_end)]
            # Align to combined index slice
            sub_index = combined.index[(combined.index >= start_ts) & (combined.index <= end_ts)]
            if len(sub_index) == 0:
                continue
            df = df.reindex(sub_index)
            valid_mask = is_row_complete(df)
            use_mask = valid_mask
            filled = int(use_mask.sum())
            if filled > 0:
                combined.loc[sub_index[use_mask], cols] = df.loc[sub_index[use_mask], cols]
                filled_total += filled
            # If still missing in this run, keep it for next source
            still_missing = combined.loc[sub_index]
            if (~is_row_complete(still_missing)).any():
                # Identify remaining sub-runs and carry over
                rem_idx = still_missing.index[~is_row_complete(still_missing)]
                sub_runs = _group_missing_runs(rem_idx, timeframe)
                new_runs.extend(sub_runs)
        refill_stats[src] += filled_total
        # Prepare for next source
        runs = new_runs
    return combined, refill_stats


# =========================
# Validation
# =========================

def validate_df(df: pd.DataFrame, timeframe: str, start_dt: datetime, end_dt: datetime, cfg: Config) -> List[str]:
    issues: List[str] = []
    # Basic schema
    expect_cols = ["open", "high", "low", "close", "volume"]
    for c in expect_cols:
        if c not in df.columns:
            issues.append(f"Missing required column: {c}")
    if not isinstance(df.index, pd.DatetimeIndex):
        issues.append("Index is not DatetimeIndex")

    # Types
    try:
        if df.index.tz is None or str(df.index.tz) != "UTC":
            issues.append("Timestamps not UTC tz-aware")
    except Exception:
        issues.append("Timestamps not tz-aware (UTC)")
    for c in expect_cols:
        if not pd.api.types.is_float_dtype(df[c]):
            issues.append(f"Column {c} is not float dtype")

    # No NaNs/Infs
    if df[expect_cols].isnull().any().any():
        issues.append("NaN values found in OHLCV")
    if np.isinf(df[expect_cols].values).any():
        issues.append("Inf values found in OHLCV")

    # No negative or zero volumes
    if (df["volume"] <= 0).any():
        issues.append("Non-positive volumes found")

    # Candle logic
    bad_open = (df["open"] < df["low"]) | (df["open"] > df["high"])
    bad_close = (df["close"] < df["low"]) | (df["close"] > df["high"])
    if bad_open.any() or bad_close.any():
        issues.append("Candle logic violated: open/close outside [low, high]")

    # Strictly increasing timestamps with fixed interval; no duplicates or gaps
    s = TF_TO_SECONDS[timeframe]
    idx = df.index.view("int64") // 10**9
    diffs = np.diff(idx)
    if (diffs <= 0).any():
        issues.append("Timestamps not strictly increasing")
    expected_step = s
    if len(diffs) > 0 and not np.all(diffs == expected_step):
        wrong = np.where(diffs != expected_step)[0]
        issues.append(f"Gaps or irregular spacing at positions: {wrong[:5].tolist()} (expected {expected_step}s)")

    # No duplicate rows
    if df.index.duplicated().any():
        issues.append("Duplicate timestamps found")

    # Outliers: adaptive based on rolling volatility (3σ bands)
    returns = df["close"].pct_change()
    # Use rolling window appropriate to timeframe
    window = _rolling_window_for_timeframe(timeframe)
    rolling_vol = returns.rolling(window=window, min_periods=max(1, window//2)).std()
    rolling_mean = returns.rolling(window=window, min_periods=max(1, window//2)).mean()
    # 3σ threshold (allows ~99.7% of normal moves under Gaussian assumption)
    threshold = rolling_mean.abs() + (3 * rolling_vol)
    outlier_mask = (returns.abs() > threshold) & (returns.notna())
    if outlier_mask.any():
        first_idx = df.index[outlier_mask][0]
        first_ret = returns[outlier_mask].iloc[0]
        issues.append(f"Outlier detected at {first_idx}: {first_ret*100:.2f}% move (outside 3σ band)")

    # Exchange consistency for BTC vs history
    if cfg.asset.upper() == "BTC":
        if (df["close"] < cfg.btc_min_usd).any() or (df["close"] > cfg.btc_max_usd).any():
            issues.append("BTC price outside plausible historical bounds")

    # End-of-window integrity: each timestamp aligns with exact tf boundary
    if cfg.enforce_window_close:
        aligned = align_to_window_close(df.index, timeframe)
        if not np.array_equal(aligned.view("int64"), df.index.view("int64")):
            issues.append("Timestamps do not represent end-of-window close times")

    # Continuous coverage and expected total rows (half-open bounds)
    start_aligned, end_exclusive = align_bounds_half_open(start_dt, end_dt, timeframe)
    # Trim a copy to the half-open range for counting
    df_trim = df[(df.index >= start_aligned) & (df.index < end_exclusive)]
    exp = expected_count_half_open(start_aligned, end_exclusive, timeframe)
    got = len(df_trim)
    if got != exp:
        issues.append(f"Expected {exp} candles in aligned range, got {got}")

    return issues


# =========================
# Output formatting
# =========================

def to_required_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index.name = "datetime"
    out = out.reset_index()
    # Required lowercase headers
    out.columns = [c.lower().strip() for c in out.columns]
    # Order
    out = out[["datetime", "open", "high", "low", "close", "volume"]]
    # Datetime formatting ISO
    out["datetime"] = pd.to_datetime(out["datetime"], utc=True)
    out["datetime"] = out["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out


def filename_for(cfg: Config) -> str:
    return f"{cfg.asset.upper()}-{cfg.timeframe}-{cfg.total_weeks}wks-data.csv"


def detect_output_dir(cfg: Config) -> str:
    return os.environ.get("LOCAL_DATA_DIR", cfg.output_dir)


def nested_output_dir(base_dir: str, cfg: Config) -> str:
    mode = (cfg.nest or "").lower()
    asset = cfg.asset.upper()
    tf = cfg.timeframe
    if mode == "asset-timeframe":
        return os.path.join(base_dir, asset, tf)
    if mode == "asset":
        return os.path.join(base_dir, asset)
    if mode == "timeframe":
        return os.path.join(base_dir, tf)
    return base_dir


# =========================
# Run
# =========================

def run(cfg: Config) -> int:
    # Resolve date range
    if cfg.start_utc and cfg.end_utc:
        start_dt = parse_iso_utc(cfg.start_utc)
        end_dt = parse_iso_utc(cfg.end_utc)
    else:
        start_dt, end_dt = derive_range_from_weeks(cfg.total_weeks, cfg.end_utc)

    # Align bounds for validation/trim (half-open)
    start_aligned, end_exclusive = align_bounds_half_open(start_dt, end_dt, cfg.timeframe)

    log_config(cfg, start_dt, end_dt, start_aligned, end_exclusive)

    # Duplicate detection: check if target file already exists
    out_base_dir = detect_output_dir(cfg)
    out_dir = nested_output_dir(out_base_dir, cfg)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename_for(cfg))
    if os.path.exists(out_path) and not cfg.overwrite:
        log_warn(f"Output already exists: {out_path}")
        log_hint("Use --overwrite to replace the existing file.")
        exp0 = expected_count_half_open(start_aligned, end_exclusive, cfg.timeframe)
        # Try to include basic info about existing file
        df_first = df_last = None
        got0 = 0
        try:
            re_df = pd.read_csv(out_path)
            if "datetime" in re_df.columns:
                dt = pd.to_datetime(re_df["datetime"], utc=True, errors="coerce")
                if len(dt) > 0 and dt.notna().any():
                    df_first = dt.min().to_pydatetime()
                    df_last = dt.max().to_pydatetime()
            got0 = len(re_df)
        except Exception:
            pass
        print_summary(True, cfg=cfg, start_aligned=start_aligned, end_exclusive=end_exclusive,
                      got_rows=got0, exp_rows=exp0, out_path=out_path, df_first=df_first, df_last=df_last,
                      reason="exists", status_text="SKIPPED", status_color=FG_YELLOW)
        return 0

    log_step("Fetching data…")
    sources_chain = getattr(cfg, "sources", None) or [cfg.source]
    df, fill_stats = fetch_with_fallbacks(cfg.asset, cfg.timeframe, start_aligned, end_exclusive, sources_chain)
    # Ensure float dtype
    df = df.astype({"open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"})
    complete = is_row_complete(df)
    exp = expected_count_half_open(start_aligned, end_exclusive, cfg.timeframe)
    got = int(complete.sum())
    missing = int(exp - got)
    log_info(f"Coverage after fallbacks → complete: {got}/{exp} • missing: {missing}")

    # Optional: print/report missing timestamps
    if missing > 0 and (cfg.print_missing or cfg.missing_report):
        miss_idx = df.index[~complete]
        preview = ", ".join([ts.isoformat() for ts in miss_idx[:10]])
        log_warn(f"First missing timestamps: {preview}{' …' if len(miss_idx) > 10 else ''}")
        if cfg.missing_report:
            try:
                with open(cfg.missing_report, 'w') as fh:
                    for ts in miss_idx:
                        fh.write(ts.isoformat()+"\n")
                log_ok(f"Missing timestamps written to {cfg.missing_report}")
            except Exception as e:
                log_warn(f"Failed to write missing report: {e}")

    # Optional: targeted gap-refill pass
    if missing > 0 and cfg.gap_refill:
        log_step("Targeted gap-refill…")
        df, refill_stats = targeted_gap_refill(cfg.asset, cfg.timeframe, df, sources_chain)
        complete = is_row_complete(df)
        got2 = int(complete.sum())
        missing2 = int(exp - got2)
        delta = got2 - got
        log_info(f"Gap-refill filled: {delta} • remaining: {missing2}")
        if missing2 > 0 and (cfg.print_missing or cfg.missing_report):
            miss_idx2 = df.index[~complete]
            preview2 = ", ".join([ts.isoformat() for ts in miss_idx2[:10]])
            log_warn(f"First remaining missing: {preview2}{' …' if len(miss_idx2) > 10 else ''}")

    print(_c(f"{E_VALIDATE} Validating data…", FG_BLUE))
    issues = validate_df(df, cfg.timeframe, start_dt, end_dt, cfg)
    if issues:
        log_error("Validation failed:")
        log_issues(issues)
        if cfg.strict:
            log_warn("Refusing to save invalid dataset.")
            exp = expected_count_half_open(start_aligned, end_exclusive, cfg.timeframe)
            # Report only complete rows in the summary to avoid confusion
            complete = is_row_complete(df)
            got = int(complete.sum())
            first = (df.index[complete].min() if got else None)
            last = (df.index[complete].max() if got else None)
            print_summary(False, cfg=cfg, start_aligned=start_aligned, end_exclusive=end_exclusive, got_rows=got, exp_rows=exp, df_first=first, df_last=last, reason="validation failed")
            return 2
        else:
            log_warn("Strict mode off; not saving.")
            exp = expected_count_half_open(start_aligned, end_exclusive, cfg.timeframe)
            complete = is_row_complete(df)
            got = int(complete.sum())
            first = (df.index[complete].min() if got else None)
            last = (df.index[complete].max() if got else None)
            print_summary(False, cfg=cfg, start_aligned=start_aligned, end_exclusive=end_exclusive, got_rows=got, exp_rows=exp, df_first=first, df_last=last, reason="strict off")
            return 2

    log_step("Formatting CSV…")
    out_df = to_required_csv(df)

    # out_dir/out_path already computed
    tmp_path = out_path + ".tmp"
    print(_c(f"{E_SAVE} Writing temp file: {tmp_path}", FG_BLUE))
    out_df.to_csv(tmp_path, index=False)

    # Final confirmation (read-back temp) then atomic replace
    print(_c("🧾 Verifying written temp file…", FG_BLUE))
    re_df = pd.read_csv(tmp_path)
    expected_cols = ["datetime", "open", "high", "low", "close", "volume"]
    if list(re_df.columns) != expected_cols:
        log_error("Written CSV has incorrect headers. Cleaning up temp.")
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return 3
    # Atomic finalize
    os.replace(tmp_path, out_path)
    log_ok("CSV ready and validated.")
    exp = expected_count_half_open(start_aligned, end_exclusive, cfg.timeframe)
    # On success, by here df is complete
    print_summary(True, cfg=cfg, start_aligned=start_aligned, end_exclusive=end_exclusive, got_rows=len(df), exp_rows=exp, out_path=out_path, df_first=df.index.min(), df_last=df.index.max())
    return 0


def parse_args_to_config(argv: List[str]) -> Config:
    p = argparse.ArgumentParser(description="Fetch, validate, and save OHLCV data CSV. If --sources is omitted, a smart prioritized chain is used to fill gaps.")
    p.add_argument("--asset", default=CONFIG.asset, help="Asset symbol, e.g., BTC")
    p.add_argument("--timeframe", default=CONFIG.timeframe, choices=list(TF_TO_SECONDS.keys()))
    p.add_argument("--weeks", type=int, default=CONFIG.total_weeks, help="Total weeks window (for filename)")
    p.add_argument("--start", dest="start_utc", default=CONFIG.start_utc, help="UTC start ISO (inclusive)")
    p.add_argument("--end", dest="end_utc", default=CONFIG.end_utc, help="UTC end ISO (inclusive)")
    p.add_argument("--source", default=CONFIG.source, choices=[
        "yahoo",
        "ccxt-binance", "ccxt-binanceus",
        "ccxt-kraken", "ccxt-bitfinex2", "ccxt-bitfinex",
        "ccxt-coinbase", "ccxt-okx", "ccxt-bybit", "ccxt-kucoin", "ccxt-bitstamp", "ccxt-gateio"
    ], help="Primary data source")
    p.add_argument("--sources", default=None, help="Comma-separated prioritized sources for fallback filling, e.g., ccxt-binance,ccxt-kraken,ccxt-coinbase")
    p.add_argument("--output-dir", default=CONFIG.output_dir, help="Output directory (overridden by LOCAL_DATA_DIR)")
    p.add_argument("--strict", action="store_true", default=CONFIG.strict, help="Fail on any validation issue")
    p.add_argument("--no-strict", dest="strict", action="store_false")
    p.add_argument("--overwrite", action="store_true", default=CONFIG.overwrite, help="Overwrite existing output file if present")
    p.add_argument("--no-overwrite", dest="overwrite", action="store_false")
    p.add_argument("--print-missing", action="store_true", default=CONFIG.print_missing, help="Print first few missing timestamps if gaps remain")
    p.add_argument("--gap-refill", action="store_true", default=CONFIG.gap_refill, help="Attempt targeted gap-refill for remaining gaps")
    p.add_argument("--missing-report", default=CONFIG.missing_report, help="Path to write all missing timestamps (one per line)")
    p.add_argument("--outlier-threshold", type=float, default=CONFIG.outlier_threshold, help="Relative change threshold for outlier rejection (e.g., 0.30 = 30%)")
    p.add_argument("--nest", default=CONFIG.nest, choices=["flat","asset","timeframe","asset-timeframe"], help="Directory nesting scheme for output")
    args = p.parse_args(argv)

    # Build sources chain
    if args.sources:
        chain = [s.strip() for s in args.sources.split(',') if s.strip()]
    else:
        # Smart default chain (deep 1m/5m/1h coverage, region-friendly first)
        smart_defaults = [
            "ccxt-bitfinex2", "ccxt-okx", "ccxt-bybit", "ccxt-binanceus",
            "ccxt-kraken", "ccxt-kucoin", "ccxt-coinbase", "ccxt-gateio",
            "ccxt-bitstamp", "ccxt-binance", "yahoo"
        ]
        # Ensure primary is first if user provided one
        chain = [args.source] + [s for s in smart_defaults if s != args.source]

    cfg = Config(
        asset=args.asset,
        timeframe=args.timeframe,
        total_weeks=args.weeks,
        start_utc=args.start_utc,
        end_utc=args.end_utc,
        source=args.source,
        sources=chain,
        output_dir=args.output_dir,
        strict=args.strict,
        overwrite=args.overwrite,
        print_missing=args.print_missing,
        gap_refill=args.gap_refill,
        missing_report=args.missing_report,
        outlier_threshold=args.outlier_threshold,
        nest=args.nest,
        btc_min_usd=CONFIG.btc_min_usd,
        btc_max_usd=CONFIG.btc_max_usd,
        enforce_window_close=CONFIG.enforce_window_close,
    )
    return cfg


if __name__ == "__main__":
    cfg = parse_args_to_config(sys.argv[1:])
    sys.exit(run(cfg))
