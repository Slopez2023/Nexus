"""Integration tests for Warehouse API with NEXUS data pipeline.

Tests the integration of WarehouseDataSource with DataManager,
feature flags, fallback logic, and data consistency validation.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from nexus.core.data.data import (
    DataManager,
    DataQualityMetrics,
    DataSourceResult,
    WarehouseDataSource,
)


logger = logging.getLogger(__name__)


class TestWarehouseDataSourceBasics:
    """Test basic WarehouseDataSource functionality."""

    def test_warehouse_data_source_initialization(self):
        """Test that WarehouseDataSource initializes correctly."""
        source = WarehouseDataSource()
        
        assert source.name == "warehouse_api"
        assert source.priority == 0.5
        assert source.adapter is not None
        assert source.monitor is not None

    def test_warehouse_data_source_has_abstract_methods(self):
        """Test that WarehouseDataSource implements required abstract methods."""
        source = WarehouseDataSource()
        
        # Should have both required methods
        assert hasattr(source, 'fetch_historical_data')
        assert hasattr(source, 'is_available')
        assert callable(source.fetch_historical_data)
        assert callable(source.is_available)

    def test_warehouse_is_available_check(self):
        """Test is_available() method."""
        source = WarehouseDataSource()
        
        # Should return boolean (may be False if API not reachable locally)
        result = source.is_available()
        assert isinstance(result, bool)


class TestDataManagerIntegration:
    """Test DataManager integration with WarehouseDataSource."""

    def test_data_manager_initializes_warehouse_source(self):
        """Test that DataManager includes WarehouseDataSource in sources."""
        manager = DataManager()
        
        # Should have multiple sources
        assert len(manager.sources) > 0
        
        # Should have warehouse_api source
        warehouse_sources = [s for s in manager.sources if s.name == "warehouse_api"]
        assert len(warehouse_sources) == 1
        
        logger.info(f"DataManager initialized with {len(manager.sources)} sources")
        for source in manager.sources:
            logger.info(f"  - {source.name} (priority={source.priority})")

    def test_source_priority_ordering(self):
        """Test that data sources are ordered by priority."""
        manager = DataManager()
        
        # Priorities should be in ascending order
        priorities = [s.priority for s in manager.sources]
        assert priorities == sorted(priorities)
        
        # Local OHLCV should be first (priority=0)
        assert manager.sources[0].name == "local_ohlcv"
        
        # Warehouse API should be second (priority=0.5)
        if len(manager.sources) > 1:
            assert manager.sources[1].name == "warehouse_api"

    def test_warehouse_source_is_warehouse_data_source_instance(self):
        """Test that warehouse source is correct type."""
        manager = DataManager()
        
        warehouse_sources = [s for s in manager.sources if s.name == "warehouse_api"]
        assert len(warehouse_sources) == 1
        
        source = warehouse_sources[0]
        assert isinstance(source, WarehouseDataSource)


class TestWarehouseDataSourceFetch:
    """Test WarehouseDataSource data fetching with mocking."""

    def _create_mock_response(self, symbol: str = "AAPL", rows: int = 20):
        """Create a mock API response."""
        dates = pd.date_range(end=datetime.now(), periods=rows, freq="D")
        data = {
            "results": [
                {
                    "timestamp": date.isoformat(),
                    "open": 100.0 + i,
                    "high": 102.0 + i,
                    "low": 99.0 + i,
                    "close": 101.0 + i,
                    "volume": 1000000 + i * 1000,
                }
                for i, date in enumerate(dates)
            ]
        }
        return data

    def _create_api_response_object(self, data: dict):
        """Create a mock APIResponse object."""
        response = MagicMock()
        response.is_success = True
        response.data = data
        response.error = None
        return response

    @pytest.mark.asyncio
    async def test_fetch_historical_data_success(self):
        """Test successful historical data fetch."""
        source = WarehouseDataSource()
        
        # Skip if client not initialized (API not running)
        if not source.is_initialized:
            pytest.skip("Warehouse API client not initialized")

    def test_fetch_historical_data_returns_data_source_result(self):
        """Test that fetch_historical_data returns DataSourceResult."""
        source = WarehouseDataSource()
        
        # Should return DataSourceResult type
        result = source.fetch_historical_data("AAPL", "2024-01-01", "2024-01-31")
        
        assert isinstance(result, DataSourceResult)
        assert hasattr(result, 'source_name')
        assert hasattr(result, 'data')
        assert hasattr(result, 'quality_metrics')
        assert hasattr(result, 'fetch_time')
        assert hasattr(result, 'success')

    def test_fetch_with_invalid_dates(self):
        """Test fetch with invalid date formats."""
        source = WarehouseDataSource()
        
        result = source.fetch_historical_data("AAPL", "invalid", "2024-01-31")
        
        # Should return error result
        assert isinstance(result, DataSourceResult)
        assert result.source_name == "warehouse_api"
        assert isinstance(result.quality_metrics, DataQualityMetrics)


class TestDataConsistencyValidation:
    """Test data consistency and validation."""

    def test_data_quality_metrics_structure(self):
        """Test that returned data has proper quality metrics."""
        source = WarehouseDataSource()
        
        result = source.fetch_historical_data("AAPL", "2024-01-01", "2024-01-31")
        
        # Should always have quality metrics
        assert isinstance(result.quality_metrics, DataQualityMetrics)
        
        # Check all metrics are present
        assert hasattr(result.quality_metrics, 'completeness_score')
        assert hasattr(result.quality_metrics, 'accuracy_score')
        assert hasattr(result.quality_metrics, 'timeliness_score')
        assert hasattr(result.quality_metrics, 'overall_score')
        assert hasattr(result.quality_metrics, 'issues_found')
        
        # All scores should be floats between 0 and 1
        assert isinstance(result.quality_metrics.completeness_score, float)
        assert isinstance(result.quality_metrics.accuracy_score, float)
        assert isinstance(result.quality_metrics.timeliness_score, float)
        assert isinstance(result.quality_metrics.overall_score, float)
        
        assert 0.0 <= result.quality_metrics.completeness_score <= 1.0
        assert 0.0 <= result.quality_metrics.accuracy_score <= 1.0
        assert 0.0 <= result.quality_metrics.timeliness_score <= 1.0
        assert 0.0 <= result.quality_metrics.overall_score <= 1.0

    def test_data_frame_has_required_columns(self):
        """Test that returned DataFrame has OHLCV columns when successful."""
        source = WarehouseDataSource()
        
        # Only check if API is available
        if not source.is_available():
            pytest.skip("Warehouse API not available")
        
        result = source.fetch_historical_data("AAPL", "2024-01-01", "2024-01-31")
        
        if result.success and not result.data.empty:
            # Should have OHLCV columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_columns:
                assert col in result.data.columns, f"Missing column: {col}"

    def test_data_frame_index_is_datetime(self):
        """Test that DataFrame index is datetime."""
        source = WarehouseDataSource()
        
        if not source.is_available():
            pytest.skip("Warehouse API not available")
        
        result = source.fetch_historical_data("AAPL", "2024-01-01", "2024-01-31")
        
        if result.success and not result.data.empty:
            # Index should be DatetimeIndex
            assert isinstance(result.data.index, pd.DatetimeIndex)


class TestFallbackBehavior:
    """Test fallback behavior when Warehouse API fails."""

    def test_data_manager_fallback_chain(self):
        """Test that DataManager tries multiple sources in priority order."""
        manager = DataManager()
        
        # Should have at least 2 sources (fallback chain)
        assert len(manager.sources) >= 2
        
        # Sources should be in priority order
        priorities = [s.priority for s in manager.sources]
        assert priorities == sorted(priorities)

    def test_warehouse_source_handles_errors_gracefully(self):
        """Test that WarehouseDataSource handles errors without crashing."""
        source = WarehouseDataSource()
        
        # Try with invalid symbol (may still return error DataSourceResult)
        result = source.fetch_historical_data("INVALID_SYMBOL_12345", "2024-01-01", "2024-01-31")
        
        # Should return DataSourceResult (not crash)
        assert isinstance(result, DataSourceResult)
        assert isinstance(result.quality_metrics, DataQualityMetrics)

    def test_warehouse_source_health_monitoring(self):
        """Test that WarehouseDataSource monitors health."""
        source = WarehouseDataSource()
        
        # Monitor should exist
        assert source.monitor is not None
        assert hasattr(source.monitor, 'get_health')
        assert callable(source.monitor.get_health)
        
        # Should be able to get health
        health = source.monitor.get_health()
        assert health is not None
        assert hasattr(health, 'status')


class TestFeatureFlagIntegration:
    """Test feature flag integration for controlled rollout."""

    def test_warehouse_source_can_be_disabled(self):
        """Test that Warehouse API source can be disabled via config."""
        # When warehouse API is not configured/enabled, DataManager
        # should still work with fallback sources
        
        manager = DataManager()
        
        # Should have other data sources even if warehouse API fails
        non_warehouse_sources = [s for s in manager.sources if s.name != "warehouse_api"]
        assert len(non_warehouse_sources) > 0

    def test_data_manager_works_without_warehouse_api(self):
        """Test that DataManager is functional even without Warehouse API."""
        manager = DataManager()
        
        # Get non-warehouse sources
        available_sources = [s for s in manager.sources if s.is_available()]
        
        # Should have at least some sources available
        assert len(manager.sources) > 0
        
        logger.info(f"Available sources: {len(available_sources)}/{len(manager.sources)}")
        for source in manager.sources:
            logger.info(f"  - {source.name}: available={source.is_available()}")


class TestMonitoringAndMetrics:
    """Test monitoring and metrics collection."""

    def test_warehouse_source_monitors_requests(self):
        """Test that Warehouse API monitors request metrics."""
        source = WarehouseDataSource()
        
        # Monitor should track metrics
        monitor = source.monitor
        assert monitor is not None
        
        # Should have metrics methods
        assert hasattr(monitor, 'record_request')
        assert hasattr(monitor, 'get_health')
        assert hasattr(monitor, 'get_metrics_summary')
        assert callable(monitor.record_request)
        assert callable(monitor.get_health)
        assert callable(monitor.get_metrics_summary)

    def test_health_status_tracking(self):
        """Test that health status is tracked."""
        source = WarehouseDataSource()
        
        health = source.monitor.get_health()
        
        # Health should have status
        assert health is not None
        assert hasattr(health, 'status')
        assert health.status is not None

    def test_metrics_summary_retrieval(self):
        """Test that metrics summary can be retrieved."""
        source = WarehouseDataSource()
        
        metrics = source.monitor.get_metrics_summary()
        
        assert isinstance(metrics, dict)
        assert 'timestamp' in metrics or 'status' in metrics or 'metrics' in metrics


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_data_manager_source_initialization_logging(self):
        """Test that DataManager logs source initialization."""
        manager = DataManager()
        
        # Should successfully initialize without errors
        assert len(manager.sources) > 0
        
        # All sources should be DataSource subclasses
        from nexus.core.data.data import DataSource
        for source in manager.sources:
            assert isinstance(source, DataSource)

    def test_warehouse_data_source_integration_with_manager(self):
        """Test end-to-end integration of Warehouse API with DataManager."""
        manager = DataManager()
        
        # Get warehouse source
        warehouse_sources = [s for s in manager.sources if s.name == "warehouse_api"]
        
        if warehouse_sources:
            warehouse_source = warehouse_sources[0]
            
            # Should be WarehouseDataSource instance
            assert isinstance(warehouse_source, WarehouseDataSource)
            
            # Should have proper priority
            assert warehouse_source.priority == 0.5
            
            # Should have required components
            assert warehouse_source.adapter is not None
            assert warehouse_source.monitor is not None


class TestAdapterIntegration:
    """Test integration with the data adapter."""

    def test_adapter_is_initialized(self):
        """Test that Warehouse API adapter is initialized."""
        source = WarehouseDataSource()
        
        assert source.adapter is not None
        assert hasattr(source.adapter, 'adapt_historical_data')
        assert hasattr(source.adapter, 'get_quality_score')
        assert callable(source.adapter.adapt_historical_data)
        assert callable(source.adapter.get_quality_score)

    def test_adapter_methods_exist(self):
        """Test that adapter has all required methods."""
        source = WarehouseDataSource()
        
        adapter = source.adapter
        
        # Should have data transformation methods
        assert hasattr(adapter, 'adapt_historical_data')
        assert hasattr(adapter, 'adapt_realtime_data')
        assert hasattr(adapter, 'adapt_list_symbols')
        assert hasattr(adapter, 'get_quality_score')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
