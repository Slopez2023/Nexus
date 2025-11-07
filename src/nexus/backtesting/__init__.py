"""Backtesting engine for quantitative trading strategies.

This package provides a professional-grade backtesting framework with:
- Realistic transaction costs and slippage
- Statistical significance testing
- Walk-forward optimization
- Comprehensive performance analysis
- Risk management and position sizing

Key Components:
- BacktestEngine: Main backtesting orchestrator
- PortfolioSimulator: Position and P&L management
- TransactionCostModel: Realistic trading costs
- PerformanceAnalyzer: Comprehensive metrics
- WalkForwardOptimizer: Overfitting prevention
- StatisticalValidator: Significance testing

Example:
    from nexus.backtesting import BacktestEngine, BacktestConfig
    from nexus.strategies import StrategyFactory

    # Configure backtest
    config = BacktestConfig(
        initial_capital=100000,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 1, 1)
    )

    # Create engine and strategy
    engine = BacktestEngine(config)
    strategy = StrategyFactory.create('rsi', period=14)

    # Run backtest
    result = engine.run_backtest(strategy, market_data)
"""

from .engine import BacktestEngine, MarketDataAdapter
from .simulator import PortfolioSimulator
from .costs import TransactionCostModel, create_realistic_cost_model
from .analyzer import PerformanceAnalyzer
from .validator import StatisticalValidator, MonteCarloResult
from .walk_forward import WalkForwardAnalyzer, WalkForwardResult
from .regime_validator import RegimeValidator, RegimeValidationResult
from .holdout_validator import HoldoutValidator, HoldoutValidationResult
from .comprehensive_report import ComprehensiveReportGenerator, ComprehensiveValidationReport
from .validation_runner import ValidationRunner
from .models import (
    BacktestConfig, BacktestResult, PortfolioState, Position, Trade,
    TradeSide, TradeCost, PerformanceMetrics, SignificanceTest,
    CostConfig, RiskLimits, WalkForwardResult, MonteCarloResult
)

__all__ = [
    "BacktestEngine",
    "MarketDataAdapter",
    "PortfolioSimulator",
    "TransactionCostModel",
    "create_realistic_cost_model",
    "PerformanceAnalyzer",
    "StatisticalValidator",
    "WalkForwardAnalyzer",
    "RegimeValidator",
    "HoldoutValidator",
    "ComprehensiveReportGenerator",
    "ValidationRunner",
    "BacktestConfig",
    "BacktestResult",
    "PortfolioState",
    "Position",
    "Trade",
    "TradeSide",
    "TradeCost",
    "PerformanceMetrics",
    "SignificanceTest",
    "WalkForwardResult",
    "MonteCarloResult",
    "RegimeValidationResult",
    "HoldoutValidationResult",
    "ComprehensiveValidationReport",
    "CostConfig",
    "RiskLimits"
]
