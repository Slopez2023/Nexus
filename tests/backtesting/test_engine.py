"""Tests for backtesting engine."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from nexus.backtesting import (
    BacktestEngine, BacktestConfig, CostConfig, RiskLimits,
    PortfolioSimulator, TransactionCostModel
)
from nexus.backtesting.models import TradeSide
from nexus.strategies import BaseStrategy, StrategyMetadata, ParameterSpec


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""

    def __init__(self, signal_threshold=0.0, **kwargs):
        self.signal_threshold = signal_threshold
        super().__init__(signal_threshold=signal_threshold, **kwargs)

    def generate_signals(self, market_data):
        """Generate mock signals."""
        from nexus.strategies import TradeSignal
        from datetime import datetime

        # Simple strategy: buy if price > threshold
        try:
            price = market_data.get_price('TEST')
            if price > self.signal_threshold:
                return [TradeSignal(
                    symbol='TEST',
                    timestamp=datetime.now(),
                    direction='long',
                    confidence=0.8,
                    reasoning='Mock signal',
                    metadata={'price': price}
                )]
        except:
            pass
        return []

    def validate_parameters(self):
        threshold = self._parameters.get('signal_threshold', self.signal_threshold)
        return isinstance(threshold, (int, float))

    @property
    def metadata(self):
        return StrategyMetadata(
            name="Mock Strategy",
            description="Test strategy",
            version="1.0.0",
            parameters={
                'signal_threshold': ParameterSpec(
                    name='signal_threshold',
                    type='float',
                    default=0.0,
                    min_value=0.0,
                    max_value=1000.0
                )
            },
            risk_profile={},
            tags=['test']
        )


class TestBacktestEngine:
    """Test backtesting engine functionality."""

    @pytest.fixture
    def sample_data(self):
        """Create sample market data."""
        dates = pd.date_range('2020-01-01', '2020-12-31', freq='D')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)

        data = pd.DataFrame({
            'open': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates)

        return data

    @pytest.fixture
    def backtest_config(self):
        """Create backtest configuration."""
        return BacktestConfig(
            initial_capital=10000.0,
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31),
            transaction_costs=CostConfig(),
            risk_limits=RiskLimits()
        )

    def test_engine_initialization(self, backtest_config):
        """Test engine initialization."""
        engine = BacktestEngine(backtest_config)
        assert engine.config == backtest_config
        assert isinstance(engine.portfolio_simulator, PortfolioSimulator)
        assert isinstance(engine.cost_model, TransactionCostModel)

    def test_data_validation(self, backtest_config, sample_data):
        """Test market data validation."""
        engine = BacktestEngine(backtest_config)

        # Valid data should pass
        engine._validate_inputs(MockStrategy(), sample_data)

        # Missing columns should fail
        invalid_data = sample_data.drop('close', axis=1)
        with pytest.raises(ValueError):
            engine._validate_inputs(MockStrategy(), invalid_data)

    def test_backtest_execution(self, backtest_config, sample_data):
        """Test basic backtest execution."""
        engine = BacktestEngine(backtest_config)
        strategy = MockStrategy(signal_threshold=95.0)  # Will generate signals

        result = engine.run_backtest(strategy, sample_data)

        assert result is not None
        assert result.config == backtest_config
        assert len(result.portfolio_states) > 0
        assert isinstance(result.performance.total_return, (int, float))
        assert result.execution_time > 0

    def test_portfolio_simulation(self, backtest_config):
        """Test portfolio simulator."""
        simulator = PortfolioSimulator(backtest_config)

        assert simulator.cash == backtest_config.initial_capital
        assert len(simulator.positions) == 0

        # Test portfolio value calculation
        value = simulator.get_portfolio_value()
        assert value == backtest_config.initial_capital

    def test_cost_model(self):
        """Test transaction cost calculations."""
        config = CostConfig()
        cost_model = TransactionCostModel(config)

        # Create a proper mock data object
        class MockMarketData:
            def get_price(self, symbol):
                return 100.0
            def get_spread(self, symbol):
                return 1.0
            def get_volume(self, symbol):
                return 10000

        # Test commission calculation
        cost = cost_model.calculate_trade_cost(
            'TEST', 100, 100.0, TradeSide.BUY,
            MockMarketData()
        )

        assert cost.total > 0
        assert cost.commission >= 0
        assert cost.slippage >= 0

    def test_zero_cost_model(self):
        """Test zero cost model."""
        from nexus.backtesting.costs import create_zero_cost_model

        class MockMarketData:
            def get_price(self, symbol):
                return 100.0
            def get_spread(self, symbol):
                return 0.0
            def get_volume(self, symbol):
                return 10000

        cost_model = create_zero_cost_model()
        cost = cost_model.calculate_trade_cost(
            'TEST', 100, 100.0, TradeSide.BUY,
            MockMarketData()
        )

        # Zero config should have zero configured costs, but slippage still
        # uses market data spread (defaults to 0.1% if spread is 0)
        assert cost.commission == 0.0
        assert cost.market_impact == 0.0
        assert cost.exchange_fees == 0.0
        assert cost.total > 0  # Has default slippage from spread calculation
