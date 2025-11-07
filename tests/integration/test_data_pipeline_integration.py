"""Integration tests for the complete data pipeline with AI analysis."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from nexus.core.data import (
    AIDataAnalyzer,
    CoinGeckoDataSource,
    DataManager,
    DataQualityMetrics,
    DataSourceResult,
    MassiveDataSource,
    YFinanceDataSource,
)


class TestDataPipelineIntegration:
    """Integration tests for the complete data pipeline."""

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return {
            "DEEPSEEK_KEY": "test_deepseek_key",
            "OPENROUTER_API_KEY": "test_openrouter_key",
            "MASSIVE_API_KEY": "test_massive_key",
            "COINGECKO_API_KEY": "test_coingecko_key"
        }

    def test_data_manager_initialization_with_config(self, sample_config):
        """Test DataManager initializes all sources correctly."""
        manager = DataManager(sample_config)

        # Should have at least 3 sources: massive, yfinance, coingecko
        assert len(manager.sources) >= 3

        # Check source types
        source_names = [s.name for s in manager.sources]
        assert "massive" in source_names
        assert "yfinance" in source_names
        assert "coingecko" in source_names

        # Check AI analyzer is configured
        assert manager.ai_analyzer.deepseek_key == "test_deepseek_key"
        assert manager.ai_analyzer.openrouter_key == "test_openrouter_key"

    @patch("nexus.core.data.data.YFinanceDataSource.is_available")
    @patch("nexus.core.data.data.MassiveDataSource.is_available")
    @patch("nexus.core.data.data.CoinGeckoDataSource.is_available")
    async def test_concurrent_data_fetching(self, mock_cg_available, mock_massive_available, mock_yf_available, sample_config):
        """Test that data fetching works concurrently from multiple sources."""
        # Mock all sources as available
        mock_cg_available.return_value = True
        mock_massive_available.return_value = True
        mock_yf_available.return_value = True

        manager = DataManager(sample_config)

        # Mock the actual fetching to return test data
        test_data = pd.DataFrame({
            "Open": [100, 101], "High": [105, 106], "Low": [95, 96],
            "Close": [102, 103], "Volume": [1000, 1100]
        })

        mock_result = DataSourceResult(
            source_name="test",
            data=test_data,
            quality_metrics=DataQualityMetrics(1.0, 1.0, 1.0, 1.0, []),
            fetch_time=1.0,
            success=True
        )

        # Mock the fetch method for all sources
        for source in manager.sources:
            source.fetch_historical_data = MagicMock(return_value=mock_result)

        # Test concurrent fetching
        results = await manager.fetch_historical_data_async("AAPL", "2023-01-01", "2023-12-31", use_ai_analysis=False)

        # Should have results from all sources
        assert "all_results" in results
        assert len(results["all_results"]) >= 3

        # Should have selected best source
        assert "best_source" in results
        assert results["best_source"] is not None

    async def test_ai_analysis_integration(self, sample_config):
        """Test AI analysis integration with data pipeline."""
        manager = DataManager(sample_config)

        # Mock AI analyzer
        manager.ai_analyzer.analyze_data_quality = AsyncMock(return_value="Test AI insights about data quality")

        # Create test data
        test_data = pd.DataFrame({
            "Close": [100, 101, 102],
            "Volume": [1000, 1100, 1200]
        })

        results = {
            "massive": DataSourceResult(
                source_name="massive",
                data=test_data,
                quality_metrics=DataQualityMetrics(1.0, 1.0, 1.0, 1.0, []),
                fetch_time=1.0,
                success=True
            )
        }

        # Add AI analysis
        await manager._add_ai_analysis(results)

        # Check that AI insights were added
        assert results["massive"].quality_metrics.ai_insights == "Test AI insights about data quality"

    def test_source_priority_and_selection(self, sample_config):
        """Test that sources are prioritized correctly and best source is selected."""
        manager = DataManager(sample_config)

        # Create mock results with different quality scores
        high_quality = DataSourceResult(
            source_name="massive",
            data=pd.DataFrame({"Close": [100]}),
            quality_metrics=DataQualityMetrics(1.0, 1.0, 1.0, 0.95, []),  # High score
            fetch_time=1.0,
            success=True
        )

        medium_quality = DataSourceResult(
            source_name="yfinance",
            data=pd.DataFrame({"Close": [100]}),
            quality_metrics=DataQualityMetrics(0.8, 0.8, 0.8, 0.75, []),  # Medium score
            fetch_time=2.0,
            success=True
        )

        low_quality = DataSourceResult(
            source_name="coingecko",
            data=pd.DataFrame({"Close": [100]}),
            quality_metrics=DataQualityMetrics(0.6, 0.6, 0.6, 0.55, []),  # Low score
            fetch_time=1.5,
            success=True
        )

        results = {
            "massive": high_quality,
            "yfinance": medium_quality,
            "coingecko": low_quality
        }

        best_source = manager._select_best_source(results)

        # Should select the highest quality source
        assert best_source == high_quality
        assert best_source.source_name == "massive"

    def test_cache_functionality(self, sample_config):
        """Test that caching works correctly."""
        manager = DataManager(sample_config)

        # Generate a cache key
        key1 = manager._generate_cache_key("AAPL", "2023-01-01", "2023-12-31", True)
        key2 = manager._generate_cache_key("AAPL", "2023-01-01", "2023-12-31", False)

        # Keys should be different when AI analysis differs
        assert key1 != key2

        # Keys should be MD5 hashes (32 characters)
        assert len(key1) == 32
        assert len(key2) == 32

    @patch("nexus.core.data.data.asyncio.new_event_loop")
    @patch("nexus.core.data.data.asyncio.set_event_loop")
    def test_sync_wrapper_functionality(self, mock_set_loop, mock_new_loop, sample_config):
        """Test that the synchronous wrapper works correctly."""
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop

        # Mock the async result
        mock_data = {"Close": [100, 101, 102]}
        mock_loop.run_until_complete.return_value = {"recommended_data": mock_data}

        manager = DataManager(sample_config)
        result = manager.fetch_historical_data("AAPL", "2023-01-01", "2023-12-31")

        # Should return a DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

        # Should have called the async function
        mock_loop.run_until_complete.assert_called_once()

    def test_error_handling_in_pipeline(self, sample_config):
        """Test that the pipeline handles errors gracefully."""
        manager = DataManager(sample_config)

        # Create results with some failures
        success_result = DataSourceResult(
            source_name="massive",
            data=pd.DataFrame({"Close": [100]}),
            quality_metrics=DataQualityMetrics(1.0, 1.0, 1.0, 1.0, []),
            fetch_time=1.0,
            success=True
        )

        failed_result = DataSourceResult(
            source_name="yfinance",
            data=pd.DataFrame(),
            quality_metrics=DataQualityMetrics(0.0, 0.0, 0.0, 0.0, ["Connection failed"]),
            fetch_time=0.0,
            success=False,
            error_message="Connection failed"
        )

        results = {"massive": success_result, "yfinance": failed_result}

        best_source = manager._select_best_source(results)

        # Should still select the successful source
        assert best_source == success_result
        assert best_source.success is True

    def test_data_quality_scoring_integration(self, sample_config):
        """Test that data quality scoring works across the pipeline."""
        manager = DataManager(sample_config)

        # Test various data quality scenarios
        test_cases = [
            # (description, data, expected_score_range)
            ("Perfect data", pd.DataFrame({
                "Open": [100], "High": [105], "Low": [95], "Close": [102], "Volume": [1000]
            }), (0.8, 1.0)),

            ("Data with gaps", pd.DataFrame({
                "Open": [100, None], "High": [105, None], "Low": [95, None],
                "Close": [102, None], "Volume": [1000, None]
            }), (0.0, 0.8)),

            ("Negative prices", pd.DataFrame({
                "Open": [100], "High": [105], "Low": [95], "Close": [-102], "Volume": [1000]
            }), (0.0, 0.8)),

            ("Empty data", pd.DataFrame(), (0.0, 0.1)),
        ]

        for description, data, expected_range in test_cases:
            score = manager.get_data_quality_score(data)
            assert expected_range[0] <= score <= expected_range[1], f"Failed for {description}: score {score}"

    def test_cross_source_data_consistency_check(self, sample_config):
        """Test checking data consistency across multiple sources."""
        manager = DataManager(sample_config)

        # Create similar data from two sources
        source1_data = pd.DataFrame({
            "Close": [100, 101, 102],
            "Volume": [1000, 1100, 1200]
        })

        source2_data = pd.DataFrame({
            "Close": [99.5, 100.8, 101.2],  # Slightly different but reasonable
            "Volume": [950, 1050, 1150]
        })

        # Both should be valid individually
        assert manager.validate_data(source1_data)
        assert manager.validate_data(source2_data)

        # Quality scores should be reasonable
        score1 = manager.get_data_quality_score(source1_data)
        score2 = manager.get_data_quality_score(source2_data)

        assert score1 > 0.7  # Good quality
        assert score2 > 0.7  # Good quality

    async def test_full_pipeline_workflow(self, sample_config):
        """Test the complete pipeline workflow from start to finish."""
        manager = DataManager(sample_config)

        # Mock all sources as available
        for source in manager.sources:
            source.is_available = MagicMock(return_value=True)

            # Mock successful data fetch
            mock_data = pd.DataFrame({
                "Open": [100], "High": [105], "Low": [95], "Close": [102], "Volume": [1000]
            })
            mock_result = DataSourceResult(
                source_name=source.name,
                data=mock_data,
                quality_metrics=DataQualityMetrics(1.0, 1.0, 1.0, 1.0, []),
                fetch_time=1.0,
                success=True
            )
            source.fetch_historical_data = MagicMock(return_value=mock_result)

        # Mock AI analysis
        manager.ai_analyzer.analyze_data_quality = AsyncMock(return_value="Mock AI analysis")

        # Run the full pipeline
        results = await manager.fetch_historical_data_async(
            "AAPL", "2023-01-01", "2023-12-31", use_ai_analysis=True
        )

        # Verify pipeline completion
        assert "symbol" in results
        assert "date_range" in results
        assert "best_source" in results
        assert "all_results" in results
        assert "recommended_data" in results
        assert "quality_assessment" in results

        # Verify AI analysis was called
        manager.ai_analyzer.analyze_data_quality.assert_called()

        # Verify we got recommended data
        assert results["recommended_data"] is not None
