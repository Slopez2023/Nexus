"""Tests for momentum strategy implementation."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from nexus.strategies import MomentumStrategy, TradeSignal, ParameterError, SignalError


class MockMarketData:
    """Mock market data for testing."""

    def __init__(self, universe=None, price_data=None, volume_data=None):
        self.universe = universe or ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
        self.price_data = price_data or {}
        self.volume_data = volume_data or {}

    def get_universe(self):
        return self.universe

    def get_price(self, symbol):
        return self.price_data.get(symbol, 100.0)

    def get_volume(self, symbol):
        return self.volume_data.get(symbol, 10000)

    def get_historical_data(self, symbol, days):
        # Return mock historical data
        base_price = self.price_data.get(symbol, 100.0)
        data = []

        # Generate declining prices for losers, increasing for winners
        if symbol == 'TSLA':  # Winner
            prices = [base_price * (0.9 + i * 0.02) for i in range(days)]
        elif symbol == 'AAPL':  # Winner
            prices = [base_price * (0.95 + i * 0.015) for i in range(days)]
        elif symbol == 'GOOGL':  # Loser
            prices = [base_price * (1.1 - i * 0.02) for i in range(days)]
        elif symbol == 'MSFT':  # Loser
            prices = [base_price * (1.05 - i * 0.015) for i in range(days)]
        else:
            prices = [base_price] * days

        for i, price in enumerate(prices):
            data.append({
                'date': (datetime.now() - timedelta(days=days-i)).isoformat(),
                'close': price
            })

        return data


class TestMomentumStrategy:
    """Test MomentumStrategy implementation."""

    def test_valid_initialization(self):
        """Test creating strategy with valid parameters."""
        strategy = MomentumStrategy(
            formation_period_months=6,
            holding_period_months=6,
            percentile=10.0,
            max_positions=None,
            min_price=1.0,
            min_volume=1000
        )

        assert strategy.get_parameter('formation_period_months') == 6
        assert strategy.get_parameter('holding_period_months') == 6
        assert strategy.get_parameter('percentile') == 10.0

    def test_invalid_parameters(self):
        """Test parameter validation."""
        # Invalid formation period
        with pytest.raises(ParameterError):
            MomentumStrategy(formation_period_months=0)

        # Invalid percentile
        with pytest.raises(ParameterError):
            MomentumStrategy(percentile=60.0)

        # Invalid max_positions
        with pytest.raises(ParameterError):
            MomentumStrategy(max_positions=0)

    def test_metadata(self):
        """Test strategy metadata."""
        strategy = MomentumStrategy()
        metadata = strategy.metadata

        assert metadata.name == "Momentum Strategy"
        assert metadata.version == "1.0.0"
        assert 'formation_period_months' in metadata.parameters
        assert metadata.risk_profile['strategy_type'] == 'momentum'
        assert 'momentum' in metadata.tags

    def test_parameter_specs(self):
        """Test parameter specifications."""
        strategy = MomentumStrategy()
        metadata = strategy.metadata

        spec = metadata.parameters['formation_period_months']
        assert spec.type == 'int'
        assert spec.default == 6
        assert spec.min_value == 1
        assert spec.max_value == 12

        spec = metadata.parameters['percentile']
        assert spec.type == 'float'
        assert spec.default == 10.0
        assert spec.min_value == 0.1
        assert spec.max_value == 50.0

    def test_generate_signals_basic(self):
        """Test basic signal generation."""
        strategy = MomentumStrategy(percentile=50.0)  # Use 50% to get 2 winners/losers

        # Mock data: TSLA and AAPL as winners, GOOGL and MSFT as losers
        market_data = MockMarketData(
            universe=['TSLA', 'AAPL', 'GOOGL', 'MSFT'],
            price_data={'TSLA': 200, 'AAPL': 150, 'GOOGL': 100, 'MSFT': 300},
            volume_data={'TSLA': 5000, 'AAPL': 2000, 'GOOGL': 1500, 'MSFT': 8000}
        )

        signals = strategy.generate_signals(market_data)

        # Should have 4 signals (2 long, 2 short)
        assert len(signals) == 4

        # Check signal structure
        for signal in signals:
            assert isinstance(signal, TradeSignal)
            assert signal.symbol in ['TSLA', 'AAPL', 'GOOGL', 'MSFT']
            assert signal.direction in ['long', 'short']
            assert 0.5 <= signal.confidence <= 1.0
            assert 'position_size' in signal.metadata
            assert signal.metadata['position_size'] == 0.25  # Equal weight: 1/(2*2)

    def test_signal_directions(self):
        """Test that winners get long signals, losers get short."""
        strategy = MomentumStrategy(percentile=50.0)

        market_data = MockMarketData(
            universe=['TSLA', 'GOOGL'],  # TSLA winner, GOOGL loser
            price_data={'TSLA': 200, 'GOOGL': 100}
        )

        signals = strategy.generate_signals(market_data)

        # Find signals for each symbol
        tsla_signal = next(s for s in signals if s.symbol == 'TSLA')
        googl_signal = next(s for s in signals if s.symbol == 'GOOGL')

        assert tsla_signal.direction == 'long'
        assert googl_signal.direction == 'short'

    def test_confidence_scoring(self):
        """Test confidence scoring based on return magnitude."""
        strategy = MomentumStrategy(percentile=100.0)  # Get all signals

        market_data = MockMarketData(
            universe=['TSLA'],  # Strong winner
            price_data={'TSLA': 200}
        )

        signals = strategy.generate_signals(market_data)
        tsla_signal = signals[0]

        # Should have high confidence for strong winner
        assert tsla_signal.confidence > 0.8

    def test_max_positions_limit(self):
        """Test max_positions parameter."""
        strategy = MomentumStrategy(percentile=50.0, max_positions=1)

        market_data = MockMarketData(
            universe=['TSLA', 'AAPL', 'GOOGL', 'MSFT']
        )

        signals = strategy.generate_signals(market_data)

        # Should have only 2 signals (1 long, 1 short) due to max_positions
        assert len(signals) == 2

    def test_price_volume_filters(self):
        """Test price and volume filtering."""
        strategy = MomentumStrategy(min_price=150.0, min_volume=3000)

        market_data = MockMarketData(
            universe=['TSLA', 'AAPL', 'GOOGL'],  # AAPL below price filter, GOOGL below volume
            price_data={'TSLA': 200, 'AAPL': 100, 'GOOGL': 100},  # AAPL too cheap
            volume_data={'TSLA': 5000, 'AAPL': 2000, 'GOOGL': 1000}  # GOOGL too low volume
        )

        signals = strategy.generate_signals(market_data)

        # Should only have TSLA signals
        symbols = {s.symbol for s in signals}
        assert symbols == {'TSLA'}

    def test_insufficient_universe(self):
        """Test handling of small universe."""
        strategy = MomentumStrategy(percentile=10.0)

        market_data = MockMarketData(universe=['TSLA'])  # Only 1 stock

        signals = strategy.generate_signals(market_data)

        # Should return empty list for insufficient stocks
        assert signals == []

    def test_signal_metadata(self):
        """Test signal metadata content."""
        strategy = MomentumStrategy()

        market_data = MockMarketData(universe=['TSLA'])

        signals = strategy.generate_signals(market_data)
        signal = signals[0]

        required_keys = [
            'strategy', 'formation_period', 'return', 'rank',
            'total_stocks', 'position_size', 'holding_months'
        ]

        for key in required_keys:
            assert key in signal.metadata

        assert signal.metadata['strategy'] == 'momentum'
        assert signal.metadata['formation_period'] == 6
        assert isinstance(signal.metadata['return'], float)
        assert signal.metadata['holding_months'] == 6

    def test_error_handling(self):
        """Test error handling in signal generation."""
        strategy = MomentumStrategy()

        # Mock market data without get_universe method
        market_data = Mock()
        del market_data.get_universe  # Remove method

        with pytest.raises(SignalError):
            strategy.generate_signals(market_data)

    def test_calculate_cumulative_return(self):
        """Test return calculation logic."""
        strategy = MomentumStrategy()

        market_data = MockMarketData()

        # Test with mock data
        ret = strategy._calculate_cumulative_return(market_data, 'TSLA', 180)  # 6 months

        # Should return a float (mock data gives positive return for TSLA)
        assert isinstance(ret, float)
        assert ret > 0  # TSLA is a winner in mock data

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        strategy = MomentumStrategy()

        # Strong winner
        confidence = strategy._calculate_confidence(0.5, 10.0, True)
        assert confidence > 0.8

        # Strong loser
        confidence = strategy._calculate_confidence(-0.5, 10.0, False)
        assert confidence > 0.8

        # Weak signal
        confidence = strategy._calculate_confidence(0.01, 10.0, True)
        assert confidence < 0.6
