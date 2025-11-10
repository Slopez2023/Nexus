"""Unit tests for Warehouse API adapter."""

import pytest
import pandas as pd
from datetime import datetime

from nexus.integrations.warehouse_api_adapter import (
    WarehouseAPIAdapter,
    DataValidationError,
)


class TestWarehouseAPIAdapter:
    """Test WarehouseAPIAdapter."""

    @pytest.fixture
    def adapter(self):
        """Provide adapter instance."""
        return WarehouseAPIAdapter()

    @pytest.fixture
    def sample_historical_response(self):
        """Provide sample historical data response."""
        return {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": 150.0,
                    "High": 152.0,
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                },
                {
                    "timestamp": "2024-01-02T00:00:00Z",
                    "Open": 151.0,
                    "High": 153.0,
                    "Low": 150.0,
                    "Close": 152.0,
                    "Volume": 1100000
                },
            ],
            "metadata": {
                "count": 2,
                "symbol": "AAPL"
            }
        }

    @pytest.fixture
    def sample_realtime_response(self):
        """Provide sample realtime data response."""
        return {
            "symbol": "AAPL",
            "price": 150.25,
            "timestamp": "2024-01-02T10:30:00Z",
            "source": "warehouse_api"
        }

    def test_adapt_historical_data_success(self, adapter, sample_historical_response):
        """Test successful historical data adaptation."""
        df = adapter.adapt_historical_data(sample_historical_response, "AAPL")

        # Check DataFrame properties
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert isinstance(df.index, pd.DatetimeIndex)

        # Check columns
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        for col in required_cols:
            assert col in df.columns

        # Check first row
        first_row = df.iloc[0]
        assert first_row["Open"] == 150.0
        assert first_row["High"] == 152.0
        assert first_row["Low"] == 149.0
        assert first_row["Close"] == 151.0
        assert first_row["Volume"] == 1000000

    def test_adapt_historical_data_empty_response(self, adapter):
        """Test handling of empty response."""
        response = {"data": []}
        df = adapter.adapt_historical_data(response, "AAPL")
        assert df.empty

    def test_adapt_historical_data_none_response(self, adapter):
        """Test handling of None response."""
        with pytest.raises(DataValidationError):
            adapter.adapt_historical_data(None, "AAPL")

    def test_adapt_historical_data_missing_columns(self, adapter):
        """Test error when required columns are missing."""
        response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": 150.0,
                    "High": 152.0,
                    # Missing Low, Close, Volume
                }
            ]
        }
        with pytest.raises(DataValidationError, match="Missing required columns"):
            adapter.adapt_historical_data(response, "AAPL")

    def test_adapt_historical_data_missing_timestamp(self, adapter):
        """Test error when timestamp is missing."""
        response = {
            "data": [
                {
                    # Missing timestamp
                    "Open": 150.0,
                    "High": 152.0,
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                }
            ]
        }
        with pytest.raises(DataValidationError, match="Missing timestamp column"):
            adapter.adapt_historical_data(response, "AAPL")

    def test_adapt_historical_data_invalid_ohlcv(self, adapter):
        """Test error when OHLCV relationships are invalid."""
        response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": 150.0,
                    "High": 148.0,  # High < Low, invalid
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                }
            ]
        }
        with pytest.raises(DataValidationError, match="OHLCV integrity issues"):
            adapter.adapt_historical_data(response, "AAPL")

    def test_adapt_historical_data_negative_prices(self, adapter):
        """Test error when prices are negative."""
        response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": -150.0,  # Negative price
                    "High": 152.0,
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                }
            ]
        }
        with pytest.raises(DataValidationError, match="OHLCV integrity issues"):
            adapter.adapt_historical_data(response, "AAPL")

    def test_adapt_realtime_data_success(self, adapter, sample_realtime_response):
        """Test successful realtime data adaptation."""
        quote = adapter.adapt_realtime_data(sample_realtime_response, "AAPL")

        assert quote["symbol"] == "AAPL"
        assert quote["price"] == 150.25
        assert "timestamp" in quote
        assert quote["source"] == "warehouse_api"
        assert quote["type"] == "realtime"

    def test_adapt_realtime_data_missing_price(self, adapter):
        """Test error when price is missing."""
        response = {
            "symbol": "AAPL",
            # Missing price
            "timestamp": "2024-01-02T10:30:00Z",
            "source": "warehouse_api"
        }
        with pytest.raises(DataValidationError, match="Missing price"):
            adapter.adapt_realtime_data(response, "AAPL")

    def test_adapt_realtime_data_missing_timestamp(self, adapter):
        """Test error when timestamp is missing."""
        response = {
            "symbol": "AAPL",
            "price": 150.25,
            # Missing timestamp
            "source": "warehouse_api"
        }
        with pytest.raises(DataValidationError, match="Missing timestamp"):
            adapter.adapt_realtime_data(response, "AAPL")

    def test_adapt_realtime_data_none_response(self, adapter):
        """Test handling of None response."""
        with pytest.raises(DataValidationError):
            adapter.adapt_realtime_data(None, "AAPL")

    def test_adapt_list_symbols_success(self, adapter):
        """Test successful symbol list adaptation."""
        response = {"symbols": ["AAPL", "GOOGL", "MSFT"]}
        symbols = adapter.adapt_list_symbols(response)

        assert isinstance(symbols, list)
        assert len(symbols) == 3
        assert all(isinstance(s, str) for s in symbols)
        assert "AAPL" in symbols

    def test_adapt_list_symbols_empty(self, adapter):
        """Test handling of empty symbol list."""
        response = {"symbols": []}
        symbols = adapter.adapt_list_symbols(response)
        assert symbols == []

    def test_adapt_list_symbols_none_response(self, adapter):
        """Test handling of None response."""
        symbols = adapter.adapt_list_symbols(None)
        assert symbols == []

    def test_quality_score_perfect_data(self, adapter):
        """Test quality score for perfect data."""
        df = pd.DataFrame({
            "Open": [150.0, 151.0, 152.0],
            "High": [152.0, 153.0, 154.0],
            "Low": [149.0, 150.0, 151.0],
            "Close": [151.0, 152.0, 153.0],
            "Volume": [1000000, 1100000, 1200000]
        })

        score = adapter.get_quality_score(df)
        assert score == 1.0

    def test_quality_score_with_nulls(self, adapter):
        """Test quality score with null values."""
        df = pd.DataFrame({
            "Open": [150.0, 151.0, None],
            "High": [152.0, 153.0, 154.0],
            "Low": [149.0, 150.0, 151.0],
            "Close": [151.0, 152.0, 153.0],
            "Volume": [1000000, 1100000, 1200000]
        })

        score = adapter.get_quality_score(df)
        assert 0.0 <= score < 1.0  # Should be less than perfect

    def test_quality_score_empty_dataframe(self, adapter):
        """Test quality score for empty DataFrame."""
        df = pd.DataFrame()
        score = adapter.get_quality_score(df)
        assert score == 0.0

    def test_quality_score_with_integrity_issues(self, adapter):
        """Test quality score with OHLCV integrity issues."""
        df = pd.DataFrame({
            "Open": [150.0, 151.0, 152.0],
            "High": [148.0, 153.0, 154.0],  # First High < Low, invalid
            "Low": [149.0, 150.0, 151.0],
            "Close": [151.0, 152.0, 153.0],
            "Volume": [1000000, 1100000, 1200000]
        })

        score = adapter.get_quality_score(df)
        assert 0.0 <= score < 1.0  # Should be less than perfect

    def test_validate_ohlcv_integrity_valid(self, adapter):
        """Test OHLCV integrity validation with valid data."""
        df = pd.DataFrame({
            "Open": [150.0, 151.0],
            "High": [152.0, 153.0],
            "Low": [149.0, 150.0],
            "Close": [151.0, 152.0],
            "Volume": [1000000, 1100000]
        }, index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"]))

        # Should not raise
        adapter._validate_ohlcv_integrity(df, "AAPL")

    def test_validate_ohlcv_integrity_high_low_reversed(self, adapter):
        """Test error when High < Low."""
        df = pd.DataFrame({
            "Open": [150.0],
            "High": [148.0],
            "Low": [149.0],
            "Close": [151.0],
            "Volume": [1000000]
        })

        with pytest.raises(DataValidationError, match="OHLCV integrity issues"):
            adapter._validate_ohlcv_integrity(df, "AAPL")

    def test_validate_ohlcv_integrity_close_outside_range(self, adapter):
        """Test error when Close is outside High-Low range."""
        df = pd.DataFrame({
            "Open": [150.0],
            "High": [152.0],
            "Low": [149.0],
            "Close": [160.0],  # Above High
            "Volume": [1000000]
        })

        with pytest.raises(DataValidationError, match="OHLCV integrity issues"):
            adapter._validate_ohlcv_integrity(df, "AAPL")

    def test_adapt_historical_data_timezone_handling(self, adapter):
        """Test that timestamps are properly handled."""
        response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "Open": 150.0,
                    "High": 152.0,
                    "Low": 149.0,
                    "Close": 151.0,
                    "Volume": 1000000
                }
            ]
        }

        df = adapter.adapt_historical_data(response, "AAPL")
        assert isinstance(df.index[0], pd.Timestamp)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
