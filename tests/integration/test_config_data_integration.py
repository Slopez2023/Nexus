"""Integration tests for config and data modules working together."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nexus.core.config import ConfigManager
from nexus.core.data import DataManager


class TestConfigDataIntegration:
    """Test integration between ConfigManager and DataManager."""

    def test_config_drives_data_manager_sources(self):
        """Test that config can specify data sources for DataManager."""
        config_data = {
            "data": {
                "sources": ["yfinance", "alpha_vantage"]
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json
            json.dump(config_data, f)
            config_file = f.name

        try:
            config_manager = ConfigManager(config_file)
            config_manager.load_config()

            # Create DataManager with sources from config
            sources = config_manager.get("data", {}).get("sources", ["yfinance"])
            data_manager = DataManager(sources)

            assert data_manager.sources == ["yfinance", "alpha_vantage"]
        finally:
            Path(config_file).unlink()

    @patch("nexus.core.data.data.pd")
    def test_data_manager_uses_config_for_fetch_params(self, mock_pd):
        """Test that DataManager could use config for fetch parameters."""
        # Mock DataFrame
        mock_df = MagicMock()
        mock_df.copy.return_value = mock_df
        mock_pd.DataFrame.return_value = mock_df

        config_data = {
            "data": {
                "default_start_date": "2023-01-01",
                "default_end_date": "2023-12-31"
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json
            json.dump(config_data, f)
            config_file = f.name

        try:
            config_manager = ConfigManager(config_file)
            config_manager.load_config()

            data_manager = DataManager()

            # Fetch using config defaults
            start_date = config_manager.get("data", {}).get("default_start_date", "2020-01-01")
            end_date = config_manager.get("data", {}).get("default_end_date", "2020-12-31")

            result = data_manager.fetch_historical_data("AAPL", start_date, end_date)

            assert result is mock_df
        finally:
            Path(config_file).unlink()

    def test_error_propagation_from_data_to_config(self):
        """Test that data errors can affect config validation."""
        # This is a conceptual test - in practice, config might validate data-related settings
        config_manager = ConfigManager()
        config_manager.set("database", {"port": "invalid"})  # Invalid port type

        with pytest.raises(Exception):  # ConfigurationError
            config_manager._validate_config()

    @patch("nexus.core.data.data.pd")
    def test_data_quality_integration_with_config_thresholds(self, mock_pd):
        """Test that data quality checks could use config thresholds."""
        # Mock DataFrame with some missing data
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.shape = (100, 5)
        mock_df.isnull.return_value.sum.return_value.sum.return_value = 10  # Some missing
        mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]
        mock_df.__getitem__.return_value.sum.return_value = 0

        config_data = {
            "data": {
                "min_quality_score": 0.9
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json
            json.dump(config_data, f)
            config_file = f.name

        try:
            config_manager = ConfigManager(config_file)
            config_manager.load_config()

            data_manager = DataManager()
            quality_score = data_manager.get_data_quality_score(mock_df)
            min_score = config_manager.get("data", {}).get("min_quality_score", 0.8)

            # Quality score is ~0.99 (1.0 - 10/500 * 0.5), which passes 0.9 threshold
            assert quality_score >= min_score
        finally:
            Path(config_file).unlink()
