"""Statistical tests for data quality validation."""

import numpy as np
from unittest.mock import MagicMock

import pytest

from nexus.core.data import DataManager


class TestDataQualityStatistics:
    """Test statistical aspects of data quality."""

    def test_data_quality_score_distribution(self):
        """Test that quality scores are properly bounded."""
        manager = DataManager()

        # Test with various data scenarios
        test_cases = [
            # (empty, expected_score)
            (True, 0.0),
            (False, 1.0),  # Perfect data
        ]

        for is_empty, expected in test_cases:
            mock_df = MagicMock()
            mock_df.empty = is_empty
            if not is_empty:
                mock_df.shape = (100, 5)
                mock_df.isnull.return_value.sum.return_value.sum.return_value = 0
                mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]
                mock_df.__getitem__.return_value.sum.return_value = 0

            score = manager.get_data_quality_score(mock_df)
            assert 0.0 <= score <= 1.0
            assert abs(score - expected) < 0.01

    def test_missing_data_impact_on_quality_score(self):
        """Test that missing data proportionally reduces quality score."""
        manager = DataManager()

        # Create mock DataFrame with known missing ratio
        missing_ratios = [0.0, 0.1, 0.2, 0.5]

        for missing_ratio in missing_ratios:
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.shape = (100, 5)  # 500 cells
            missing_cells = int(500 * missing_ratio)
            mock_df.isnull.return_value.sum.return_value.sum.return_value = missing_cells
            mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]
            mock_df.__getitem__.return_value.sum.return_value = 0

            score = manager.get_data_quality_score(mock_df)
            expected_score = 1.0 - missing_ratio * 0.5

            assert abs(score - expected_score) < 0.01

    def test_negative_price_detection(self):
        """Test detection of negative prices affects quality score."""
        manager = DataManager()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.shape = (100, 5)
        mock_df.isnull.return_value.sum.return_value.sum.return_value = 0
        mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]

        # Test with no negative prices
        mock_df.__getitem__.return_value.sum.return_value = 0
        score_no_negative = manager.get_data_quality_score(mock_df)

        # Test with some negative prices
        mock_df.__getitem__.return_value.sum.return_value = 5  # 5 negative prices
        score_with_negative = manager.get_data_quality_score(mock_df)

        assert score_with_negative < score_no_negative
        assert score_with_negative == 0.8  # 1.0 - 0.2

    def test_data_validation_statistical_properties(self):
        """Test statistical properties of data validation."""
        manager = DataManager()

        # Test that validation is deterministic
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]

        # Run validation multiple times
        results = [manager.validate_data(mock_df) for _ in range(10)]
        assert all(results)  # All should be True for this mock

    @pytest.mark.parametrize("missing_ratio,expected_score_reduction", [
        (0.0, 0.0),
        (0.1, 0.05),  # 10% missing -> 5% score reduction
        (0.2, 0.1),
        (0.5, 0.25),
    ])
    def test_missing_data_score_parametrized(self, missing_ratio, expected_score_reduction):
        """Parametrized test for missing data impact."""
        manager = DataManager()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.shape = (100, 5)
        missing_cells = int(500 * missing_ratio)
        mock_df.isnull.return_value.sum.return_value.sum.return_value = missing_cells
        mock_df.columns = ["Open", "High", "Low", "Close", "Volume"]
        mock_df.__getitem__.return_value.sum.return_value = 0

        score = manager.get_data_quality_score(mock_df)
        expected_score = 1.0 - expected_score_reduction

        assert abs(score - expected_score) < 0.01

    def test_quality_score_extremes(self):
        """Test quality score at extreme values."""
        manager = DataManager()

        # Perfect data
        mock_perfect = MagicMock()
        mock_perfect.empty = False
        mock_perfect.shape = (100, 5)
        mock_perfect.isnull.return_value.sum.return_value.sum.return_value = 0
        mock_perfect.columns = ["Open", "High", "Low", "Close", "Volume"]
        mock_perfect.__getitem__.return_value.sum.return_value = 0

        perfect_score = manager.get_data_quality_score(mock_perfect)
        assert perfect_score == 1.0

        # Terrible data: all missing + negative prices
        mock_terrible = MagicMock()
        mock_terrible.empty = False
        mock_terrible.shape = (100, 5)
        mock_terrible.isnull.return_value.sum.return_value.sum.return_value = 500  # All missing
        mock_terrible.columns = ["Open", "High", "Low", "Close", "Volume"]
        mock_terrible.__getitem__.return_value.sum.return_value = 100  # All negative

        terrible_score = manager.get_data_quality_score(mock_terrible)
        assert terrible_score == 0.0  # Should be clamped to 0.0
