"""Data models for backtesting engine.

Professional data structures for backtesting with full type safety
and validation. All models are immutable where appropriate.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import pandas as pd
import numpy as np


class TradeSide(Enum):
    """Trading side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class Trade:
    """Individual trade execution record."""
    timestamp: datetime
    symbol: str
    side: TradeSide
    quantity: int
    price: float
    commission: float
    slippage: float
    total_cost: float

    @property
    def net_amount(self) -> float:
        """Net cash flow from trade."""
        multiplier = 1 if self.side == TradeSide.BUY else -1
        return multiplier * self.quantity * self.price + self.total_cost


@dataclass
class Position:
    """Current position in a security."""
    symbol: str
    quantity: int
    average_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0

    def update_market_price(self, price: float) -> None:
        """Update position with current market price."""
        self.market_value = self.quantity * price
        self.unrealized_pnl = (price - self.average_price) * self.quantity

    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0


@dataclass
class PortfolioState:
    """Complete portfolio state at a point in time."""
    timestamp: datetime
    cash: float
    positions: Dict[str, Position]
    total_value: float = 0.0
    daily_return: float = 0.0

    def __post_init__(self):
        """Calculate total portfolio value."""
        position_value = sum(pos.market_value for pos in self.positions.values())
        self.total_value = self.cash + position_value


@dataclass
class TradeCost:
    """Breakdown of trading costs."""
    commission: float
    slippage: float
    market_impact: float
    exchange_fees: float
    total: float

    @classmethod
    def zero(cls) -> 'TradeCost':
        """Create zero cost structure."""
        return cls(0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""
    initial_capital: float
    start_date: datetime
    end_date: datetime
    transaction_costs: 'CostConfig'
    risk_limits: 'RiskLimits'
    benchmark_symbol: Optional[str] = None
    rebalance_frequency: str = "daily"  # daily, weekly, monthly

    def __post_init__(self):
        """Validate configuration."""
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")


@dataclass
class CostConfig:
    """Transaction cost configuration."""
    commission_per_share: float = 0.005  # $0.005 per share
    commission_minimum: float = 1.0      # $1 minimum
    commission_maximum: Optional[float] = None
    slippage_bps: float = 5.0            # 5 basis points
    market_impact_bps: float = 2.0       # 2 basis points
    exchange_fees: float = 0.0001        # 0.01% exchange fees


@dataclass
class RiskLimits:
    """Portfolio risk limits."""
    max_position_size_pct: float = 0.10  # Max 10% in single position
    max_drawdown_pct: float = 0.20       # Max 20% drawdown
    max_leverage: float = 1.0            # No leverage by default
    max_daily_loss_pct: float = 0.05     # Max 5% daily loss


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float
    best_trade: float
    worst_trade: float
    alpha: Optional[float] = None
    beta: Optional[float] = None

    # Confidence intervals
    sharpe_ci_lower: Optional[float] = None
    sharpe_ci_upper: Optional[float] = None
    return_ci_lower: Optional[float] = None
    return_ci_upper: Optional[float] = None


@dataclass
class SignificanceTest:
    """Statistical significance test results."""
    p_value: float
    test_statistic: float
    confidence_level: float
    is_significant: bool
    effect_size: float
    sample_size: int
    test_type: str  # "sharpe", "t-test", "bootstrap"


@dataclass
class BacktestResult:
    """Complete backtest result with all data."""
    config: BacktestConfig
    portfolio_states: List[PortfolioState]
    trades: List[Trade]
    performance: PerformanceMetrics
    significance_tests: List[SignificanceTest]
    equity_curve: pd.Series
    drawdowns: pd.Series
    monthly_returns: pd.Series
    risk_metrics: Dict[str, float]

    # Execution metadata
    execution_time: float
    data_quality_score: float
    warnings: List[str]


@dataclass
class WalkForwardResult:
    """Results from walk-forward optimization."""
    config: BacktestConfig
    window_results: List[BacktestResult]
    optimal_parameters: Dict[str, Any]
    parameter_performance: Dict[str, List[float]]
    stability_score: float
    out_of_sample_performance: PerformanceMetrics


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    n_simulations: int
    return_distribution: np.ndarray
    sharpe_distribution: np.ndarray
    max_drawdown_distribution: np.ndarray
    failure_rate: float  # Percentage of simulations with negative returns
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    confidence_intervals: Dict[str, tuple[float, float]]


@dataclass
class RiskDecomposition:
    """Portfolio risk decomposition."""
    total_risk: float
    systematic_risk: float
    idiosyncratic_risk: float
    factor_exposures: Dict[str, float]
    risk_contributions: Dict[str, float]


# Utility functions
def calculate_returns(portfolio_states: List[PortfolioState]) -> pd.Series:
    """Calculate returns from portfolio states."""
    values = [state.total_value for state in portfolio_states]
    returns = pd.Series(values).pct_change().dropna()
    returns.index = [state.timestamp for state in portfolio_states[1:]]
    return returns


def calculate_drawdowns(portfolio_states: List[PortfolioState]) -> pd.Series:
    """Calculate drawdowns from portfolio states."""
    values = pd.Series([state.total_value for state in portfolio_states])
    rolling_max = values.expanding().max()
    drawdowns = (values - rolling_max) / rolling_max
    drawdowns.index = [state.timestamp for state in portfolio_states]
    return drawdowns


def calculate_max_drawdown(portfolio_states: List[PortfolioState]) -> float:
    """Calculate maximum drawdown."""
    drawdowns = calculate_drawdowns(portfolio_states)
    return abs(drawdowns.min())


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio."""
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
    if excess_returns.std() == 0:
        return 0.0

    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)  # Annualized


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sortino ratio."""
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0

    return excess_returns.mean() / downside_returns.std() * np.sqrt(252)


def calculate_win_rate(returns: pd.Series) -> float:
    """Calculate win rate (percentage of positive returns)."""
    if len(returns) == 0:
        return 0.0
    return (returns > 0).sum() / len(returns)


def calculate_profit_factor(returns: pd.Series) -> float:
    """Calculate profit factor (gross profits / gross losses)."""
    gross_profits = returns[returns > 0].sum()
    gross_losses = abs(returns[returns < 0].sum())

    if gross_losses == 0:
        return float('inf') if gross_profits > 0 else 0.0

    return gross_profits / gross_losses
