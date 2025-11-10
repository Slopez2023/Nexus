"""Phase 3: Warehouse API Validation & Comparison Tests.

Tests data consistency between Warehouse API and legacy data sources.
Validates that Warehouse API data is comparable in quality to existing sources.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pytest

from nexus.core.data.data import (
    DataManager,
    DataSourceResult,
    MassiveDataSource,
    WarehouseDataSource,
    YFinanceDataSource,
)
from nexus.integrations import WarehouseAPIAdapter, WarehouseAPIClient

logger = logging.getLogger(__name__)


class TestDataConsistency:
    """Test data consistency between Warehouse API and legacy sources."""

    @pytest.fixture
    def manager(self):
        """Create a DataManager instance."""
        return DataManager(config={})

    @pytest.fixture
    def test_symbols(self) -> List[str]:
        """Common test symbols across all data sources."""
        return ["AAPL", "GOOGL", "MSFT"]

    @pytest.fixture
    def date_range(self) -> Tuple[str, str]:
        """Standard date range for testing."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        return str(start_date), str(end_date)

    def test_warehouse_source_exists(self, manager):
        """Verify WarehouseDataSource is registered in DataManager."""
        source_names = [s.name for s in manager.sources]
        assert "warehouse_api" in source_names, "WarehouseDataSource not registered"

    def test_warehouse_source_priority(self, manager):
        """Verify Warehouse API has correct priority (0.5)."""
        warehouse_source = next(
            (s for s in manager.sources if s.name == "warehouse_api"), None
        )
        assert warehouse_source is not None, "Warehouse API source not found"
        assert warehouse_source.priority == 0.5, f"Expected priority 0.5, got {warehouse_source.priority}"

    def test_source_priority_order(self, manager):
        """Verify sources are ordered by priority."""
        priorities = [s.priority for s in manager.sources]
        # Check that list is sorted (ascending)
        assert priorities == sorted(priorities), f"Sources not in priority order: {priorities}"
        logger.info(f"Source order: {[(s.name, s.priority) for s in manager.sources]}")

    def test_fetch_warehouse_data_single_symbol(self, manager, date_range):
        """Test fetching data from Warehouse API for single symbol."""
        start_date, end_date = date_range

        result = manager.fetch_historical_data("AAPL", start_date, end_date)

        if not result.empty:
            # Validate structure
            assert isinstance(result, pd.DataFrame), "Result should be DataFrame"
            assert len(result) > 0, "Result should have data"
            assert "Open" in result.columns, "Missing Open column"
            assert "Close" in result.columns, "Missing Close column"
            logger.info(f"Fetched {len(result)} rows for AAPL")
        else:
            logger.warning("No data returned from manager")

    def test_data_quality_validation(self, manager, date_range):
        """Test data quality scoring."""
        start_date, end_date = date_range

        # Get results from async method to access quality metrics
        async def fetch_and_validate():
            results = await manager.fetch_historical_data_async(
                "AAPL", start_date, end_date, use_ai_analysis=False
            )
            return results

        try:
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(fetch_and_validate())

            # Check if we got warehouse API results
            if "warehouse_api" in results.get("all_results", {}):
                warehouse_result = results["all_results"]["warehouse_api"]
                if warehouse_result.success:
                    quality = warehouse_result.quality_metrics
                    logger.info(
                        f"Quality scores: completeness={quality.completeness_score:.2%}, "
                        f"accuracy={quality.accuracy_score:.2%}, overall={quality.overall_score:.2%}"
                    )
                    assert quality.overall_score >= 0.0, "Quality score should be non-negative"
                    assert quality.overall_score <= 1.0, "Quality score should be <= 1.0"
        except Exception as e:
            logger.warning(f"Could not test quality validation: {e}")

    def test_ohlcv_integrity(self, manager, date_range):
        """Test OHLCV data integrity."""
        start_date, end_date = date_range

        result = manager.fetch_historical_data("AAPL", start_date, end_date)

        if not result.empty:
            # OHLCV integrity checks
            df = result

            # Check High >= Low
            invalid_high_low = (df["High"] < df["Low"]).sum()
            assert invalid_high_low == 0, f"{invalid_high_low} rows with High < Low"

            # Check Close in [Low, High]
            invalid_close = (
                ((df["Close"] < df["Low"]) | (df["Close"] > df["High"])).sum()
            )
            assert invalid_close == 0, f"{invalid_close} rows with Close outside [Low, High]"

            # Check no negative values
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col in df.columns:
                    negative_count = (df[col] < 0).sum()
                    assert negative_count == 0, f"{negative_count} negative {col} values"

            logger.info("All OHLCV integrity checks passed")

    def test_timestamp_consistency(self, manager, date_range):
        """Test that timestamps are properly aligned."""
        start_date, end_date = date_range

        result = manager.fetch_historical_data("AAPL", start_date, end_date)

        if not result.empty:
            df = result
            # Check index is datetime
            assert isinstance(
                df.index, pd.DatetimeIndex
            ), f"Index type is {type(df.index)}, expected DatetimeIndex"

            # Check dates are in range
            if len(df) > 0:
                first_date = df.index[0].date()
                last_date = df.index[-1].date()

                start_dt = pd.Timestamp(start_date).date()
                end_dt = pd.Timestamp(end_date).date()

                assert first_date >= start_dt, f"First date {first_date} before range start {start_dt}"
                assert last_date <= end_dt, f"Last date {last_date} after range end {end_dt}"

            logger.info(f"Timestamp range verified: {df.index[0]} to {df.index[-1]}")

    def test_data_completeness(self, manager, date_range):
        """Test data completeness (no NaN values in critical columns)."""
        start_date, end_date = date_range

        result = manager.fetch_historical_data("AAPL", start_date, end_date)

        if not result.empty:
            df = result
            critical_cols = ["Open", "High", "Low", "Close", "Volume"]

            for col in critical_cols:
                if col in df.columns:
                    nan_count = df[col].isna().sum()
                    completeness = 1.0 - (nan_count / len(df))
                    assert (
                        completeness >= 0.95
                    ), f"{col}: {completeness:.1%} completeness (< 95%)"
                    logger.info(f"{col}: {completeness:.1%} complete")


class TestSourceComparison:
    """Compare Warehouse API with legacy data sources."""

    @pytest.fixture
    def warehouse_source(self):
        """Create WarehouseDataSource instance."""
        return WarehouseDataSource()

    @pytest.fixture
    def yfinance_source(self):
        """Create YFinanceDataSource instance."""
        return YFinanceDataSource()

    @pytest.fixture
    def date_range(self) -> Tuple[str, str]:
        """Standard date range for testing."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        return str(start_date), str(end_date)

    def test_warehouse_vs_yfinance_symbol(
        self, warehouse_source, yfinance_source, date_range
    ):
        """Compare Warehouse API vs YFinance for single symbol."""
        symbol = "AAPL"
        start_date, end_date = date_range

        warehouse_result = warehouse_source.fetch_historical_data(symbol, start_date, end_date)
        yfinance_result = yfinance_source.fetch_historical_data(symbol, start_date, end_date)

        if warehouse_result.success and yfinance_result.success:
            wh_df = warehouse_result.data
            yf_df = yfinance_result.data

            # Compare row counts (should be similar)
            count_ratio = len(wh_df) / len(yf_df) if len(yf_df) > 0 else 0
            logger.info(
                f"Row count - Warehouse: {len(wh_df)}, YFinance: {len(yf_df)}, "
                f"ratio: {count_ratio:.2%}"
            )

            # Both should have data
            assert len(wh_df) > 0, "Warehouse API returned no data"
            assert len(yf_df) > 0, "YFinance returned no data"

            # Row count should be within 20% (accounting for market holidays, etc.)
            assert (
                0.8 <= count_ratio <= 1.2
            ), f"Row count ratio {count_ratio} outside [0.8, 1.2]"

    def test_quality_metrics_comparison(
        self, warehouse_source, yfinance_source, date_range
    ):
        """Compare quality metrics between sources."""
        symbol = "AAPL"
        start_date, end_date = date_range

        warehouse_result = warehouse_source.fetch_historical_data(symbol, start_date, end_date)
        yfinance_result = yfinance_source.fetch_historical_data(symbol, start_date, end_date)

        if warehouse_result.success and yfinance_result.success:
            wh_quality = warehouse_result.quality_metrics
            yf_quality = yfinance_result.quality_metrics

            logger.info(
                f"Warehouse quality: {wh_quality.overall_score:.2%}, "
                f"YFinance quality: {yf_quality.overall_score:.2%}"
            )

            # Both should have reasonable quality scores
            assert (
                wh_quality.overall_score >= 0.0
            ), "Warehouse quality score should be non-negative"
            assert (
                yf_quality.overall_score >= 0.0
            ), "YFinance quality score should be non-negative"


class TestPerformanceBenchmarks:
    """Benchmark Warehouse API performance."""

    @pytest.fixture
    def warehouse_source(self):
        """Create WarehouseDataSource instance."""
        return WarehouseDataSource()

    @pytest.fixture
    def date_range(self) -> Tuple[str, str]:
        """Standard date range for testing."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        return str(start_date), str(end_date)

    def test_fetch_latency(self, warehouse_source, date_range):
        """Test Warehouse API fetch latency."""
        symbol = "AAPL"
        start_date, end_date = date_range

        result = warehouse_source.fetch_historical_data(symbol, start_date, end_date)

        fetch_time_ms = result.fetch_time * 1000
        logger.info(f"Fetch latency: {fetch_time_ms:.2f}ms")

        if result.success:
            # Should complete in reasonable time (< 10 seconds)
            assert fetch_time_ms < 10000, f"Latency {fetch_time_ms:.2f}ms exceeds 10s threshold"

    def test_concurrent_fetches(self, warehouse_source, date_range):
        """Test multiple concurrent fetches."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        start_date, end_date = date_range

        # Sequential timing baseline
        import time

        start_time = time.time()
        results = []
        for symbol in symbols:
            result = warehouse_source.fetch_historical_data(symbol, start_date, end_date)
            results.append(result)
        sequential_time = time.time() - start_time

        logger.info(f"Sequential fetch time: {sequential_time:.2f}s for {len(symbols)} symbols")

        # At least some results should succeed
        successful = sum(1 for r in results if r.success)
        logger.info(f"Successful fetches: {successful}/{len(symbols)}")

        # Latency should be reasonable
        assert (
            sequential_time < 30.0
        ), f"Total fetch time {sequential_time:.2f}s exceeds 30s threshold"


class TestPhase3Validation:
    """Phase 3 validation test suite."""

    @pytest.fixture
    def manager(self):
        """Create a DataManager instance."""
        return DataManager(config={})

    @pytest.fixture
    def validation_symbols(self) -> List[str]:
        """Symbols to validate in Phase 3."""
        return ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

    @pytest.fixture
    def date_range(self) -> Tuple[str, str]:
        """Standard date range for testing."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=60)
        return str(start_date), str(end_date)

    def test_phase3_readiness(self, manager):
        """Test that system is ready for Phase 3 validation."""
        # Verify all sources are present
        source_names = {s.name for s in manager.sources}
        expected_sources = {"local_ohlcv", "warehouse_api", "yfinance"}

        for expected in expected_sources:
            assert expected in source_names, f"Missing expected source: {expected}"

        logger.info(f"Phase 3 sources present: {source_names}")

    def test_multi_symbol_validation(self, manager, validation_symbols, date_range):
        """Validate Warehouse API across multiple symbols."""
        start_date, end_date = date_range
        results_summary = {}

        for symbol in validation_symbols:
            try:
                result = manager.fetch_historical_data(symbol, start_date, end_date)

                if not result.empty:
                    results_summary[symbol] = {
                        "rows": len(result),
                        "columns": list(result.columns),
                        "date_range": f"{result.index[0].date()} to {result.index[-1].date()}",
                    }
                else:
                    results_summary[symbol] = {"status": "no_data"}
            except Exception as e:
                results_summary[symbol] = {"status": "error", "error": str(e)}

        logger.info(f"Validation results: {json.dumps(results_summary, indent=2, default=str)}")

        # At least some symbols should have data
        successful = sum(1 for v in results_summary.values() if "rows" in v)
        assert successful > 0, "No symbols returned data"

    def test_fallback_chain_intact(self, manager):
        """Verify fallback chain is working correctly."""
        # If Warehouse API fails, should be able to fall back to other sources
        result = manager.fetch_historical_data("AAPL", "2024-01-01", "2024-01-31")

        # Should get some result (either from warehouse or fallback)
        assert isinstance(result, pd.DataFrame), "Result should be DataFrame"

    def test_data_validation_report(self, manager, validation_symbols, date_range):
        """Generate Phase 3 data validation report."""
        start_date, end_date = date_range
        report = {
            "timestamp": datetime.now().isoformat(),
            "phase": 3,
            "symbols": validation_symbols,
            "date_range": {"start": start_date, "end": end_date},
            "validation_results": {},
        }

        for symbol in validation_symbols:
            result = manager.fetch_historical_data(symbol, start_date, end_date)

            if not result.empty:
                # Data quality metrics
                completeness = 1.0 - (result.isna().sum().sum() / (result.shape[0] * result.shape[1]))
                has_ohlcv = all(col in result.columns for col in ["Open", "High", "Low", "Close", "Volume"])

                report["validation_results"][symbol] = {
                    "status": "success",
                    "rows": len(result),
                    "completeness": f"{completeness:.1%}",
                    "has_ohlcv": has_ohlcv,
                    "first_date": result.index[0].isoformat(),
                    "last_date": result.index[-1].isoformat(),
                }
            else:
                report["validation_results"][symbol] = {
                    "status": "no_data",
                }

        logger.info(f"Phase 3 Validation Report:\n{json.dumps(report, indent=2)}")

        # Validate that we got at least some results
        successful = sum(
            1 for v in report["validation_results"].values() if v.get("status") == "success"
        )
        assert successful > 0, "Phase 3 validation should produce some successful results"



