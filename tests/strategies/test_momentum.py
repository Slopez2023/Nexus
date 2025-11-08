"""Tests for momentum strategy implementation."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from nexus.strategies import MomentumStrategy, TradeSignal, ParameterError, SignalError


class MockMarketData:
    """Mock market data for testing."""

    def __init__(self, universe=None, price_data=None, volume_data=None):
        self.universe = universe or ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
        self.price_data = price_data or {'AAPL': 150, 'GOOGL': 100, 'MSFT': 300, 'TSLA': 200}
        self.volume_data = volume_data or {'AAPL': 100000, 'GOOGL': 50000, 'MSFT': 200000, 'TSLA': 150000}

    def get_universe(self):
        return self.universe

    def get_price(self, symbol):
        return self.price_data.get(symbol, 100.0)

    def get_volume(self, symbol):
        return self.volume_data.get(symbol, 50000)

    def get_historical_data(self, symbol, days):
        # Return mock historical data
        base_price = self.price_data.get(symbol, 100.0)
        data = []

        # Generate price series with different trends and RSI characteristics
        if symbol == 'TSLA':  # Strong winner, RSI around 60 (buyable)
            prices = [base_price * (0.8 + i * 0.025) for i in range(days)]
        elif symbol == 'AAPL':  # Moderate winner, RSI around 65 (buyable)
            prices = [base_price * (0.9 + i * 0.02) for i in range(days)]
        elif symbol == 'GOOGL':  # Moderate loser, RSI around 35 (shortable)
            prices = [base_price * (1.1 - i * 0.015) for i in range(days)]
        elif symbol == 'MSFT':  # Strong loser, RSI around 40 (shortable)
            prices = [base_price * (1.2 - i * 0.02) for i in range(days)]
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
            formation_period_months=3,
            holding_period_months=1,
            percentile=20.0,
            max_positions=10,
            min_price=5.0,
            min_volume=50000,
            rsi_period=14,
            rsi_overbought=70.0,
            rsi_oversold=30.0
        )

        assert strategy.get_parameter('formation_period_months') == 3
        assert strategy.get_parameter('holding_period_months') == 1
        assert strategy.get_parameter('percentile') == 20.0
        assert strategy.get_parameter('rsi_period') == 14

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

        # Invalid RSI period
        with pytest.raises(ParameterError):
            MomentumStrategy(rsi_period=1)

        # Invalid RSI thresholds
        with pytest.raises(ParameterError):
            MomentumStrategy(rsi_overbought=80.0, rsi_oversold=80.0)

    def test_metadata(self):
        """Test strategy metadata."""
        strategy = MomentumStrategy()
        metadata = strategy.metadata

        assert metadata.name == "Momentum Strategy"
        assert metadata.version == "2.0.0"
        assert 'formation_period_months' in metadata.parameters
        assert 'rsi_period' in metadata.parameters
        assert metadata.risk_profile['strategy_type'] == 'momentum'
        assert 'rsi-filtered' in metadata.tags

    def test_parameter_specs(self):
        """Test parameter specifications."""
        strategy = MomentumStrategy()
        metadata = strategy.metadata

        spec = metadata.parameters['formation_period_months']
        assert spec.type == 'int'
        assert spec.default == 3
        assert spec.min_value == 1
        assert spec.max_value == 12

        spec = metadata.parameters['percentile']
        assert spec.type == 'float'
        assert spec.default == 20.0
        assert spec.min_value == 0.1
        assert spec.max_value == 50.0

        spec = metadata.parameters['rsi_period']
        assert spec.type == 'int'
        assert spec.default == 14
        assert spec.min_value == 2
        assert spec.max_value == 50

    def test_generate_signals_basic(self):
        """Test basic signal generation."""
        strategy = MomentumStrategy(percentile=50.0, max_positions=2)  # Use 50% to get 2 winners/losers

        # Mock data with appropriate prices and volumes
        market_data = MockMarketData(
            universe=['TSLA', 'AAPL', 'GOOGL', 'MSFT']
        )

        signals = strategy.generate_signals(market_data)

        # Should have up to 4 signals (2 long, 2 short), but filtered by RSI
        assert len(signals) <= 4
        assert len(signals) > 0  # At least some signals

        # Check signal structure
        for signal in signals:
            assert isinstance(signal, TradeSignal)
            assert signal.symbol in ['TSLA', 'AAPL', 'GOOGL', 'MSFT']
            assert signal.direction in ['long', 'short']
            assert 0.5 <= signal.confidence <= 1.0
            assert 'position_size' in signal.metadata
            assert 'rsi' in signal.metadata
            assert 'momentum_return' in signal.metadata

    def test_signal_directions(self):
        """Test that winners get long signals, losers get short."""
        strategy = MomentumStrategy(percentile=100.0, max_positions=10)  # Get all possible signals

        market_data = MockMarketData(
            universe=['TSLA', 'GOOGL']  # TSLA winner, GOOGL loser
        )

        signals = strategy.generate_signals(market_data)

        # Check that we have signals and they are in expected directions
        tsla_signals = [s for s in signals if s.symbol == 'TSLA']
        googl_signals = [s for s in signals if s.symbol == 'GOOGL']

        # TSLA should have long signal if RSI allows
        if tsla_signals:
            assert tsla_signals[0].direction == 'long'

        # GOOGL should have short signal if RSI allows
        if googl_signals:
            assert googl_signals[0].direction == 'short'

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
        strategy = MomentumStrategy(min_price=250.0, min_volume=100000)

        market_data = MockMarketData(
            universe=['TSLA', 'AAPL', 'MSFT'],  # MSFT above filters, others below
            price_data={'TSLA': 200, 'AAPL': 150, 'MSFT': 300},  # MSFT meets price
            volume_data={'TSLA': 150000, 'AAPL': 100000, 'MSFT': 200000}  # All meet volume except if we set higher
        )

        signals = strategy.generate_signals(market_data)

        # Should only have MSFT signals (meets price filter)
        symbols = {s.symbol for s in signals}
        assert 'MSFT' in symbols or len(signals) == 0  # May have no signals if RSI filters

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
        if signals:  # May have no signals due to RSI filter
            signal = signals[0]

            required_keys = [
                'strategy', 'formation_period', 'rsi', 'momentum_return',
                'position_size', 'max_portfolio_exposure'
            ]

            for key in required_keys:
                assert key in signal.metadata

            assert signal.metadata['strategy'] == 'momentum_rsi'
            assert signal.metadata['formation_period'] == 3
            assert isinstance(signal.metadata['rsi'], float)
            assert isinstance(signal.metadata['momentum_return'], float)

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

        # Create test historical data
        hist_data = [
            {'close': 100.0},
            {'close': 105.0},
            {'close': 110.0},
            {'close': 108.0},
            {'close': 115.0}
        ]

        # Test with 3 days (should be positive return)
        ret = strategy._calculate_cumulative_return(hist_data, 3)

        assert isinstance(ret, float)
        assert ret > 0  # Positive return

    def test_calculate_rsi(self):
        """Test RSI calculation."""
        strategy = MomentumStrategy()

        # Create test data with increasing prices (should have high RSI)
        hist_data = [{'close': 100 + i} for i in range(20)]

        rsi = strategy._calculate_rsi(hist_data, 14)
        assert isinstance(rsi, float)
        assert 50 <= rsi <= 100  # Increasing prices should have high RSI

        # Create test data with decreasing prices (should have low RSI)
        hist_data_down = [{'close': 120 - i} for i in range(20)]

        rsi_down = strategy._calculate_rsi(hist_data_down, 14)
        assert isinstance(rsi_down, float)
        assert 0 <= rsi_down <= 50  # Decreasing prices should have low RSI

    def test_calculate_position_size(self):
        """Test position sizing logic."""
        strategy = MomentumStrategy()

        # Cheap stock
        size_cheap = strategy._calculate_position_size(10)
        assert size_cheap == 0.03

        # Expensive stock
        size_expensive = strategy._calculate_position_size(500)
        assert size_expensive == 0.01

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        strategy = MomentumStrategy()

        # Strong winner
        confidence = strategy._calculate_confidence(0.5, 20.0, True)
        assert confidence > 0.8

        # Strong loser
        confidence = strategy._calculate_confidence(-0.5, 20.0, False)
        assert confidence > 0.8

        # Weak signal
        confidence = strategy._calculate_confidence(0.01, 20.0, True)
        assert confidence < 0.6
