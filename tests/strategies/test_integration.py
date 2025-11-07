"""Integration tests for strategy framework components."""

import pytest
from unittest.mock import Mock
from datetime import datetime

from nexus.strategies import (
    BaseStrategy,
    TradeSignal,
    StrategyFactory,
    StrategyMetadata,
    ParameterSpec,
    MarketData,
)


class MockMarketData(MarketData):
    """Mock market data for testing."""

    def __init__(self, price_data=None):
        self.price_data = price_data or {"AAPL": 150.0, "GOOGL": 2800.0}

    def get_price(self, symbol: str) -> float:
        return self.price_data.get(symbol, 100.0)

    def get_volume(self, symbol: str) -> int:
        return 1000000

    def get_historical_data(self, symbol: str, days: int):
        # Return mock historical data
        return [{"date": datetime.now(), "price": 150.0, "volume": 1000000}]


class SimpleMovingAverageStrategy(BaseStrategy):
    """Simple test strategy for integration testing."""

    def generate_signals(self, market_data: MarketData) -> list[TradeSignal]:
        """Generate signals based on mock logic."""
        signals = []

        for symbol in ["AAPL", "GOOGL"]:
            price = market_data.get_price(symbol)

            # Simple logic: buy if price > 100
            if price > 100:
                signals.append(TradeSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    direction="long",
                    confidence=0.8,
                    reasoning=f"Price {price} > threshold",
                    metadata={"price": price, "threshold": 100}
                ))

        return signals

    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        threshold = self.get_parameter("threshold", 100)
        return isinstance(threshold, (int, float)) and threshold > 0

    @property
    def metadata(self) -> StrategyMetadata:
        """Strategy metadata."""
        return StrategyMetadata(
            name="Simple Moving Average Strategy",
            description="Basic test strategy for integration testing",
            version="1.0.0",
            parameters={
                "threshold": ParameterSpec(
                    name="threshold",
                    type="float",
                    default=100.0,
                    min_value=0.0,
                    max_value=10000.0,
                    description="Price threshold for signals"
                )
            },
            risk_profile={
                "max_drawdown": 0.1,
                "sharpe_target": 1.5
            },
            tags=["test", "simple"],
            author="NEXUS Test Suite"
        )


class TestStrategyFrameworkIntegration:
    """Integration tests for the complete strategy framework."""

    def setup_method(self):
        """Clear registry before each test."""
        StrategyFactory.clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        StrategyFactory.clear_registry()

    def test_full_strategy_lifecycle(self):
        """Test complete strategy lifecycle: register -> create -> use."""
        # Register strategy
        StrategyFactory.register(SimpleMovingAverageStrategy)

        # Verify registration
        assert "simple" in StrategyFactory.list_strategies()
        info = StrategyFactory.get_strategy_info("simple")
        assert info["class"] == "SimpleMovingAverageStrategy"

        # Create strategy instance
        strategy = StrategyFactory.create("simple", threshold=120.0)

        # Verify strategy creation
        assert isinstance(strategy, SimpleMovingAverageStrategy)
        assert strategy.get_parameter("threshold") == 120.0

        # Create mock market data
        market_data = MockMarketData({"AAPL": 130.0, "GOOGL": 50.0})

        # Generate signals
        signals = strategy.generate_signals(market_data)

        # Verify signals
        assert len(signals) == 1  # Only AAPL should trigger
        signal = signals[0]
        assert signal.symbol == "AAPL"
        assert signal.direction == "long"
        assert signal.confidence == 0.8
        assert "Price 130.0 > threshold" in signal.reasoning
        assert signal.metadata["price"] == 130.0
        assert signal.metadata["threshold"] == 120.0  # Strategy parameter

    def test_strategy_parameter_validation_integration(self):
        """Test parameter validation through the full factory -> strategy flow."""
        StrategyFactory.register(SimpleMovingAverageStrategy)

        # Valid parameters
        strategy = StrategyFactory.create("simple", threshold=200.0)
        assert strategy.validate_parameters() is True

        # Invalid parameters should fail at creation
        with pytest.raises(Exception):  # ParameterError from validation
            StrategyFactory.create("simple", threshold=-10.0)

    def test_multiple_strategies_integration(self):
        """Test multiple strategies working together."""
        # Register multiple strategies
        StrategyFactory.register(SimpleMovingAverageStrategy)

        # Create instances with different parameters
        strategy1 = StrategyFactory.create("simple", threshold=100.0)
        strategy2 = StrategyFactory.create("simple", threshold=200.0)

        # Test with same market data
        market_data = MockMarketData({"AAPL": 150.0})

        signals1 = strategy1.generate_signals(market_data)
        signals2 = strategy2.generate_signals(market_data)

        # Both should generate signals (AAPL price 150 > both thresholds)
        assert len(signals1) == 1
        assert len(signals2) == 1

        # But different metadata due to different thresholds
        assert signals1[0].metadata["threshold"] == 100.0
        assert signals2[0].metadata["threshold"] == 200.0

    def test_signal_serialization_integration(self):
        """Test signal serialization/deserialization in full context."""
        StrategyFactory.register(SimpleMovingAverageStrategy)
        strategy = StrategyFactory.create("simple", threshold=100.0)

        market_data = MockMarketData({"AAPL": 150.0})
        signals = strategy.generate_signals(market_data)

        assert len(signals) == 1
        original_signal = signals[0]

        # Serialize
        data = original_signal.to_dict()

        # Deserialize
        restored_signal = TradeSignal.from_dict(data)

        # Verify complete round-trip
        assert restored_signal == original_signal
        assert restored_signal.symbol == original_signal.symbol
        assert restored_signal.direction == original_signal.direction
        assert restored_signal.confidence == original_signal.confidence
        assert restored_signal.metadata == original_signal.metadata

    def test_error_handling_integration(self):
        """Test error handling throughout the framework."""
        StrategyFactory.register(SimpleMovingAverageStrategy)

        # Test invalid strategy creation
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyFactory.create("nonexistent")

        # Test strategy with invalid parameters
        with pytest.raises(Exception):  # Should fail parameter validation
            StrategyFactory.create("simple", threshold="invalid")

    def test_metadata_integration(self):
        """Test metadata access and validation."""
        StrategyFactory.register(SimpleMovingAverageStrategy)

        info = StrategyFactory.get_strategy_info("simple")
        metadata = info["metadata"]

        assert metadata.name == "Simple Moving Average Strategy"
        assert metadata.version == "1.0.0"
        assert "threshold" in metadata.parameters

        # Test parameter validation through metadata
        errors = metadata.validate_parameters({"threshold": 150.0})
        assert errors == []

        errors = metadata.validate_parameters({"threshold": -10.0})
        assert len(errors) > 0

        errors = metadata.validate_parameters({"invalid_param": 100.0})
        assert len(errors) > 0

    def test_performance_integration(self):
        """Test performance of integrated components."""
        import time

        StrategyFactory.register(SimpleMovingAverageStrategy)

        # Create multiple strategies
        strategies = []
        for i in range(10):
            strategies.append(StrategyFactory.create("simple", threshold=100.0 + i))

        market_data = MockMarketData({"AAPL": 200.0, "GOOGL": 3000.0, "MSFT": 300.0})

        # Measure signal generation performance
        start_time = time.time()
        total_signals = 0

        for _ in range(100):  # 100 iterations
            for strategy in strategies:
                signals = strategy.generate_signals(market_data)
                total_signals += len(signals)

        end_time = time.time()

        duration = end_time - start_time
        signals_per_second = total_signals / duration

        # Should handle reasonable performance (at least 1000 signals/second)
        assert signals_per_second > 1000, f"Performance too low: {signals_per_second} signals/sec"
        print(".2f")
        print(f"Total signals generated: {total_signals}")

    def test_registry_isolation(self):
        """Test that registry operations don't interfere between tests."""
        # This test ensures proper cleanup between tests
        initial_count = StrategyFactory.get_registry_size()

        StrategyFactory.register(SimpleMovingAverageStrategy)
        assert StrategyFactory.get_registry_size() == initial_count + 1

        # Cleanup happens in teardown_method
        # Next test should start clean
