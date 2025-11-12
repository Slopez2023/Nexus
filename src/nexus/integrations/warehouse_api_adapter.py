"""Adapter to convert Warehouse API responses to NEXUS data models.

Ensures backward compatibility with existing code by converting
Warehouse API response format to the internal data format used
throughout NEXUS.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
from datetime import datetime

from nexus.core.logging_config import get_nexus_logger


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


class WarehouseAPIAdapter:
    """Converts Warehouse API responses to NEXUS data models."""

    def __init__(self):
        self.logger = get_nexus_logger(__name__)

    def adapt_historical_data(
        self,
        api_response: Dict[str, Any],
        symbol: str
    ) -> pd.DataFrame:
        """Convert historical data from Warehouse API to DataFrame.

        Expected Warehouse API format:
        {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": 150.0,
                    "High": 152.0,
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                },
                ...
            ],
            "metadata": {...}
        }

        Returns DataFrame with DatetimeIndex and OHLCV columns.

        Args:
            api_response: Response from Warehouse API
            symbol: Trading symbol (for logging)

        Returns:
            DataFrame with OHLCV data indexed by timestamp

        Raises:
            DataValidationError: If data format is invalid or incomplete
        """
        try:
            if not api_response:
                raise DataValidationError("API response is empty")

            data_list = api_response.get("data", [])
            if not data_list:
                self.logger.warning(f"No data received for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(data_list)

            # Normalize column names to uppercase (handle both uppercase and lowercase)
            column_mapping = {
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume',
                'time': 'timestamp'
            }
            
            new_columns = {}
            for col in df.columns:
                lower_col = col.lower()
                if lower_col in column_mapping:
                    new_columns[col] = column_mapping[lower_col]
            
            df = df.rename(columns=new_columns)
            
            # Validate required columns
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise DataValidationError(
                    f"Missing required columns for {symbol}: {missing_cols}"
                )

            # Convert timestamp to datetime index
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
            else:
                raise DataValidationError(f"Missing timestamp column for {symbol}")

            # Ensure correct data types (only convert if not already numeric)
            for col in required_cols:
                if col in df.columns:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = pd.to_numeric(df[col], errors="coerce")

            # Remove any rows with NaN values in OHLCV columns only
            initial_len = len(df)
            df = df.dropna(subset=required_cols)
            if len(df) < initial_len:
                self.logger.warning(
                    f"Dropped {initial_len - len(df)} rows with NaN in OHLCV columns for {symbol}"
                )

            # Sort by timestamp
            df.sort_index(inplace=True)

            # Validate data integrity
            self._validate_ohlcv_integrity(df, symbol)

            self.logger.debug(
                f"Successfully adapted historical data for {symbol}",
                extra={"rows": len(df), "date_range": f"{df.index[0]} to {df.index[-1]}"}
            )

            return df

        except DataValidationError:
            raise
        except Exception as e:
            error_msg = f"Failed to adapt historical data for {symbol}: {str(e)}"
            self.logger.error(error_msg)
            raise DataValidationError(error_msg) from e

    def adapt_realtime_data(
        self,
        api_response: Dict[str, Any],
        symbol: str
    ) -> Dict[str, Any]:
        """Convert real-time quote from Warehouse API to standard format.

        Expected Warehouse API format:
        {
            "symbol": "AAPL",
            "price": 150.25,
            "timestamp": "2024-01-01T10:30:00Z",
            "source": "warehouse_api"
        }

        Returns standardized quote format.

        Args:
            api_response: Response from Warehouse API
            symbol: Trading symbol (for validation)

        Returns:
            Standardized quote dictionary

        Raises:
            DataValidationError: If data format is invalid
        """
        try:
            if not api_response:
                raise DataValidationError("API response is empty")

            # Extract fields
            price = api_response.get("price")
            timestamp = api_response.get("timestamp")
            source = api_response.get("source", "warehouse_api")

            # Validate required fields
            if price is None:
                raise DataValidationError(f"Missing price for {symbol}")
            if timestamp is None:
                raise DataValidationError(f"Missing timestamp for {symbol}")

            # Convert to standard format
            quote = {
                "symbol": symbol,
                "price": float(price),
                "timestamp": pd.to_datetime(timestamp).isoformat(),
                "source": source,
                "type": "realtime"
            }

            self.logger.debug(
                f"Successfully adapted real-time data for {symbol}",
                extra={"price": price}
            )

            return quote

        except DataValidationError:
            raise
        except Exception as e:
            error_msg = f"Failed to adapt real-time data for {symbol}: {str(e)}"
            self.logger.error(error_msg)
            raise DataValidationError(error_msg) from e

    def adapt_list_symbols(
        self,
        api_response: Dict[str, Any]
    ) -> List[str]:
        """Convert symbol list from Warehouse API.

        Args:
            api_response: Response from Warehouse API

        Returns:
            List of symbols

        Raises:
            DataValidationError: If data format is invalid
        """
        try:
            if not api_response:
                return []

            symbols = api_response.get("symbols", [])
            if not isinstance(symbols, list):
                raise DataValidationError("Symbols should be a list")

            # Ensure all are strings and non-empty
            symbols = [str(s).strip().upper() for s in symbols if s]

            return symbols

        except DataValidationError:
            raise
        except Exception as e:
            error_msg = f"Failed to adapt symbol list: {str(e)}"
            self.logger.error(error_msg)
            raise DataValidationError(error_msg) from e

    def _validate_ohlcv_integrity(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> None:
        """Validate OHLCV data integrity.

        Checks:
        - High >= Low
        - High >= Close >= Low >= 0
        - Volume >= 0
        - No gaps in data (optional warning)

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol (for logging)

        Raises:
            DataValidationError: If integrity checks fail
        """
        issues = []

        # Check High >= Low
        invalid_hl = df[df["High"] < df["Low"]]
        if len(invalid_hl) > 0:
            issues.append(f"{len(invalid_hl)} rows with High < Low")

        # Check Close within High-Low range
        invalid_close = df[(df["Close"] > df["High"]) | (df["Close"] < df["Low"])]
        if len(invalid_close) > 0:
            issues.append(f"{len(invalid_close)} rows with Close outside High-Low range")

        # Check for negative prices
        negative_prices = df[(df["Open"] < 0) | (df["High"] < 0) | 
                            (df["Low"] < 0) | (df["Close"] < 0)]
        if len(negative_prices) > 0:
            issues.append(f"{len(negative_prices)} rows with negative prices")

        # Check for negative volume
        negative_volume = df[df["Volume"] < 0]
        if len(negative_volume) > 0:
            issues.append(f"{len(negative_volume)} rows with negative volume")

        if issues:
            error_msg = f"OHLCV integrity issues for {symbol}: {'; '.join(issues)}"
            self.logger.error(error_msg)
            raise DataValidationError(error_msg)

        # Warn about potential gaps
        if len(df) > 1:
            date_diffs = df.index.to_series().diff()
            # Detect gaps larger than 2 days (for daily data)
            large_gaps = date_diffs[date_diffs.dt.days > 2]
            if len(large_gaps) > 0:
                self.logger.warning(
                    f"Detected {len(large_gaps)} potential data gaps for {symbol}"
                )

    def get_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate data quality score (0.0 - 1.0).

        Factors:
        - Completeness: % of non-null OHLCV values
        - Consistency: % of rows with valid OHLCV relationships
        - Recency: Recent data vs old data

        Args:
            df: Historical data DataFrame

        Returns:
            Quality score between 0.0 and 1.0
        """
        if df.empty:
            return 0.0

        try:
            # Completeness score
            total_values = len(df) * 5  # OHLCV columns
            null_values = df[["Open", "High", "Low", "Close", "Volume"]].isna().sum().sum()
            completeness = 1.0 - (null_values / total_values) if total_values > 0 else 0.0

            # Consistency score
            consistency_issues = 0
            if len(df) > 0:
                if (df["High"] < df["Low"]).any():
                    consistency_issues += (df["High"] < df["Low"]).sum()
                if (df["Close"] > df["High"]).any() or (df["Close"] < df["Low"]).any():
                    consistency_issues += (
                        (df["Close"] > df["High"]) | (df["Close"] < df["Low"])
                    ).sum()
                if (df["Open"] < 0).any() or (df["High"] < 0).any():
                    consistency_issues += (
                        (df["Open"] < 0) | (df["High"] < 0) | 
                        (df["Low"] < 0) | (df["Close"] < 0)
                    ).sum()

            consistency = 1.0 - (consistency_issues / len(df)) if len(df) > 0 else 0.0

            # Combined score (weighted)
            quality_score = (completeness * 0.6) + (consistency * 0.4)

            return max(0.0, min(1.0, quality_score))

        except Exception as e:
            self.logger.error(f"Error calculating quality score: {str(e)}")
            return 0.0
