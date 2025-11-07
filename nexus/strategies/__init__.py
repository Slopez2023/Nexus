"""Trading strategy framework.

This package provides the core framework for implementing and managing
trading strategies in the NEXUS system. All strategies must inherit from
BaseStrategy and be registered with the StrategyFactory.

Key Components:
- BaseStrategy: Abstract base class for all strategies
- TradeSignal: Immutable signal representation
- StrategyFactory: Registry for strategy creation
- StrategyMetadata: Strategy information and configuration
- ParameterSpec: Parameter validation specifications

Example:
    from nexus.strategies import BaseStrategy, TradeSignal, StrategyFactory

    class MyStrategy(BaseStrategy):
        def generate_signals(self, market_data):
            return [TradeSignal(...)]
        # ... other methods

    StrategyFactory.register(MyStrategy)
    strategy = StrategyFactory.create('my', param1=value1)
"""

from .base import (
    BaseStrategy,
    TradeSignal,
    StrategyMetadata,
    ParameterSpec,
    MarketData,
    StrategyError,
    ParameterError,
    SignalError,
    ValidationError,
)
from .factory import StrategyFactory

__all__ = [
    "BaseStrategy",
    "TradeSignal",
    "StrategyMetadata",
    "ParameterSpec",
    "MarketData",
    "StrategyError",
    "ParameterError",
    "SignalError",
    "ValidationError",
    "StrategyFactory",
]
