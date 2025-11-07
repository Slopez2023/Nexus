"""Multi-regime validation for strategy performance across market conditions.

Integrates market regime detection with validation to test strategy
robustness across bull, bear, sideways, and high-volatility markets.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import logging

import pandas as pd
import numpy as np

from .regime_detector import MarketRegimeDetector, MarketRegime, RegimePeriod
from .validator import StatisticalValidator
from .analyzer import PerformanceAnalyzer
from .models import PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class RegimeValidationResult:
    """Results of multi-regime validation."""
    overall_performance: PerformanceMetrics
    regime_performance: Dict[str, PerformanceMetrics]
    regime_distribution: Dict[str, float]  # Percentage of time in each regime
    regime_transitions: Dict[str, Dict[str, int]]  # Transition matrix
    regime_stability_score: float  # How consistent performance is across regimes
    regime_adaptability_score: float  # How well strategy adapts to regime changes
    best_regime: str
    worst_regime: str
    regime_risk_adjusted_alpha: Dict[str, float]  # Risk-adjusted excess returns by regime


class RegimeValidator:
    """Multi-regime strategy validation.

    Tests strategy performance across different market regimes:
    - Bull markets (strong uptrends)
    - Bear markets (strong downtrends)
    - Sideways markets (range-bound)
    - High volatility periods (stress events)
    """

    def __init__(
        self,
        regime_detector_config: Optional[Dict[str, Any]] = None,
        benchmark_returns: Optional[pd.Series] = None
    ):
        """Initialize regime validator.

        Args:
            regime_detector_config: Configuration for regime detection
            benchmark_returns: Benchmark returns for comparison
        """
        self.regime_detector_config = regime_detector_config or {}
        self.regime_detector = MarketRegimeDetector(**self.regime_detector_config)
        self.statistical_validator = StatisticalValidator()
        self.performance_analyzer = PerformanceAnalyzer()
        self.benchmark_returns = benchmark_returns

    def validate_strategy_regime_performance(
        self,
        strategy_returns: pd.Series,
        price_data: pd.Series,
        strategy_func: Optional[Callable] = None,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> RegimeValidationResult:
        """Validate strategy performance across market regimes.

        Args:
            strategy_returns: Daily strategy returns with datetime index
            price_data: Underlying price data with datetime index
            strategy_func: Optional strategy function for re-generation
            strategy_params: Optional strategy parameters

        Returns:
            RegimeValidationResult: Complete regime analysis
        """
        logger.info("Starting multi-regime validation")

        # Detect market regimes
        regime_periods = self.regime_detector.detect_regimes(price_data)

        if not regime_periods:
            logger.warning("No regime periods detected")
            return self._create_empty_result()

        logger.info(f"Detected {len(regime_periods)} regime periods")

        # Calculate performance by regime
        regime_performance = self._calculate_regime_performance(
            strategy_returns, price_data, regime_periods
        )

        # Calculate overall performance
        overall_performance = self._calculate_overall_performance(strategy_returns)

        # Calculate regime distribution
        regime_distribution = self._calculate_regime_distribution(regime_periods, price_data)

        # Calculate regime transitions
        regime_transitions = self._calculate_regime_transitions(regime_periods)

        # Calculate regime stability metrics
        regime_stability_score = self._calculate_regime_stability(regime_performance)
        regime_adaptability_score = self._calculate_regime_adaptability(regime_performance)

        # Find best and worst regimes
        best_regime = max(regime_performance.keys(),
                         key=lambda r: regime_performance[r].sharpe_ratio)
        worst_regime = min(regime_performance.keys(),
                          key=lambda r: regime_performance[r].sharpe_ratio)

        # Calculate risk-adjusted alpha by regime
        regime_risk_adjusted_alpha = self._calculate_regime_alpha(
            regime_performance, price_data, regime_periods
        )

        result = RegimeValidationResult(
            overall_performance=overall_performance,
            regime_performance=regime_performance,
            regime_distribution=regime_distribution,
            regime_transitions=regime_transitions,
            regime_stability_score=regime_stability_score,
            regime_adaptability_score=regime_adaptability_score,
            best_regime=best_regime,
            worst_regime=worst_regime,
            regime_risk_adjusted_alpha=regime_risk_adjusted_alpha
        )

        logger.info(f"Regime validation complete. Stability: {regime_stability_score:.3f}")
        return result

    def _calculate_regime_performance(
        self,
        strategy_returns: pd.Series,
        price_data: pd.Series,
        regime_periods: List[RegimePeriod]
    ) -> Dict[str, PerformanceMetrics]:
        """Calculate performance metrics for each regime.

        Args:
            strategy_returns: Strategy returns
            price_data: Price data
            regime_periods: Detected regime periods

        Returns:
            Dictionary of performance metrics by regime
        """
        regime_performance = {}

        for regime in MarketRegime:
            regime_dates = []
            for period in regime_periods:
                if period.regime == regime:
                    date_range = pd.date_range(period.start_date, period.end_date, freq='D')
                    regime_dates.extend(date_range)

            if not regime_dates:
                # Create empty performance for regime with no data
                regime_performance[regime.value] = PerformanceMetrics(
                    total_return=0.0, annualized_return=0.0, volatility=0.0,
                    sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                    calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                    total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
                )
                continue

            # Filter regime_dates to only include dates that exist in the data
            available_dates = set(strategy_returns.index) & set(price_data.index)
            regime_dates = [d for d in regime_dates if d in available_dates]

            if not regime_dates:
                # Create empty performance if no matching dates
                regime_performance[regime.value] = PerformanceMetrics(
                    total_return=0.0, annualized_return=0.0, volatility=0.0,
                    sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                    calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                    total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
                )
                continue

            # Ensure regime_dates are sorted and unique
            regime_dates = sorted(list(set(regime_dates)))

            # Filter data for this regime - use intersection to ensure alignment
            regime_strategy_returns = strategy_returns[strategy_returns.index.isin(regime_dates)]
            regime_price_data = price_data[price_data.index.isin(regime_dates)]

            # Ensure both series have the same index after filtering
            common_index = regime_strategy_returns.index.intersection(regime_price_data.index)
            regime_strategy_returns = regime_strategy_returns.loc[common_index]
            regime_price_data = regime_price_data.loc[common_index]

            if len(regime_strategy_returns) < 5:  # Minimum data requirement
                regime_performance[regime.value] = PerformanceMetrics(
                    total_return=0.0, annualized_return=0.0, volatility=0.0,
                    sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                    calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                    total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
                )
                continue

            # Calculate comprehensive metrics
            total_return = (1 + regime_strategy_returns).prod() - 1

            # Time weighting
            days = len(regime_strategy_returns)
            years = days / 252  # Trading days
            annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

            volatility = regime_strategy_returns.std() * np.sqrt(252)

            # Risk-adjusted metrics
            sharpe_ratio = (regime_strategy_returns.mean() / regime_strategy_returns.std() * np.sqrt(252)
                          if regime_strategy_returns.std() > 0 else 0.0)

            downside_returns = regime_strategy_returns[regime_strategy_returns < 0]
            sortino_ratio = (regime_strategy_returns.mean() / downside_returns.std() * np.sqrt(252)
                           if len(downside_returns) > 0 and downside_returns.std() > 0 else 0.0)

            # Drawdown analysis
            if len(regime_price_data) > 0:
                # Use price data for drawdown calculation if available
                equity_curve = (1 + regime_strategy_returns).cumprod()
                rolling_max = equity_curve.expanding().max()
                drawdowns = (equity_curve - rolling_max) / rolling_max
                max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0
            else:
                max_drawdown = 0.0

            calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0

            # Trade metrics
            win_rate = (regime_strategy_returns > 0).mean()

            gross_profits = regime_strategy_returns[regime_strategy_returns > 0].sum()
            gross_losses = abs(regime_strategy_returns[regime_strategy_returns < 0].sum())
            profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')

            # Simplified trade metrics
            total_trades = len(regime_strategy_returns)
            avg_trade_pnl = regime_strategy_returns.mean()
            best_trade = regime_strategy_returns.max()
            worst_trade = regime_strategy_returns.min()

            regime_performance[regime.value] = PerformanceMetrics(
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                calmar_ratio=calmar_ratio,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                avg_trade_pnl=avg_trade_pnl,
                best_trade=best_trade,
                worst_trade=worst_trade
            )

        return regime_performance

    def _calculate_overall_performance(self, strategy_returns: pd.Series) -> PerformanceMetrics:
        """Calculate overall strategy performance.

        Args:
            strategy_returns: Strategy returns

        Returns:
            Overall performance metrics
        """
        if len(strategy_returns) == 0:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        total_return = (1 + strategy_returns).prod() - 1
        days = len(strategy_returns)
        years = days / 252
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
        volatility = strategy_returns.std() * np.sqrt(252)

        sharpe_ratio = (strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
                      if strategy_returns.std() > 0 else 0.0)

        downside_returns = strategy_returns[strategy_returns < 0]
        sortino_ratio = (strategy_returns.mean() / downside_returns.std() * np.sqrt(252)
                       if len(downside_returns) > 0 and downside_returns.std() > 0 else 0.0)

        # Max drawdown
        equity_curve = (1 + strategy_returns).cumprod()
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())

        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        win_rate = (strategy_returns > 0).mean()

        gross_profits = strategy_returns[strategy_returns > 0].sum()
        gross_losses = abs(strategy_returns[strategy_returns < 0].sum())
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(strategy_returns),
            avg_trade_pnl=strategy_returns.mean(),
            best_trade=strategy_returns.max(),
            worst_trade=strategy_returns.min()
        )

    def _calculate_regime_distribution(
        self,
        regime_periods: List[RegimePeriod],
        price_data: pd.Series
    ) -> Dict[str, float]:
        """Calculate the distribution of time spent in each regime.

        Args:
            regime_periods: Detected regime periods
            price_data: Price data for total time calculation

        Returns:
            Percentage of time in each regime
        """
        total_days = len(price_data)
        if total_days == 0:
            return {regime.value: 0.0 for regime in MarketRegime}

        regime_days = {regime.value: 0 for regime in MarketRegime}

        for period in regime_periods:
            days_in_period = (period.end_date - period.start_date).days + 1
            regime_days[period.regime.value] += days_in_period

        # Convert to percentages
        return {
            regime: (days / total_days) * 100
            for regime, days in regime_days.items()
        }

    def _calculate_regime_transitions(self, regime_periods: List[RegimePeriod]) -> Dict[str, Dict[str, int]]:
        """Calculate regime transition matrix.

        Args:
            regime_periods: Detected regime periods

        Returns:
            Transition matrix showing regime changes
        """
        transitions = {
            from_regime.value: {to_regime.value: 0 for to_regime in MarketRegime}
            for from_regime in MarketRegime
        }

        if len(regime_periods) < 2:
            return transitions

        for i in range(len(regime_periods) - 1):
            from_regime = regime_periods[i].regime.value
            to_regime = regime_periods[i + 1].regime.value
            transitions[from_regime][to_regime] += 1

        return transitions

    def _calculate_regime_stability(self, regime_performance: Dict[str, PerformanceMetrics]) -> float:
        """Calculate regime stability score.

        Measures how consistent strategy performance is across regimes.
        Higher score means more stable performance across market conditions.

        Args:
            regime_performance: Performance by regime

        Returns:
            Stability score (0-1)
        """
        sharpe_ratios = [
            perf.sharpe_ratio for perf in regime_performance.values()
            if perf.total_trades > 0  # Only include regimes with data
        ]

        if len(sharpe_ratios) < 2:
            return 0.0

        # Calculate coefficient of variation of Sharpe ratios
        mean_sharpe = np.mean(sharpe_ratios)
        std_sharpe = np.std(sharpe_ratios)

        if mean_sharpe == 0:
            return 0.0

        cv = std_sharpe / abs(mean_sharpe)

        # Convert to stability score (lower CV = higher stability)
        stability = 1 / (1 + cv)

        return stability

    def _calculate_regime_adaptability(self, regime_performance: Dict[str, PerformanceMetrics]) -> float:
        """Calculate regime adaptability score.

        Measures how well the strategy adapts to different market conditions.
        Higher score means better adaptation (profitable in more regimes).

        Args:
            regime_performance: Performance by regime

        Returns:
            Adaptability score (0-1)
        """
        profitable_regimes = sum(
            1 for perf in regime_performance.values()
            if perf.sharpe_ratio > 0 and perf.total_trades > 0
        )

        total_regimes = len([perf for perf in regime_performance.values() if perf.total_trades > 0])

        if total_regimes == 0:
            return 0.0

        # Percentage of regimes where strategy is profitable
        adaptability = profitable_regimes / total_regimes

        return adaptability

    def _calculate_regime_alpha(
        self,
        regime_performance: Dict[str, PerformanceMetrics],
        price_data: pd.Series,
        regime_periods: List[RegimePeriod]
    ) -> Dict[str, float]:
        """Calculate risk-adjusted alpha by regime.

        Args:
            regime_performance: Performance by regime
            price_data: Price data
            regime_periods: Regime periods

        Returns:
            Alpha by regime
        """
        regime_alpha = {}

        if self.benchmark_returns is None:
            # Use buy-and-hold as benchmark
            benchmark_returns = price_data.pct_change().dropna()
        else:
            benchmark_returns = self.benchmark_returns

        for regime in MarketRegime:
            regime_dates = []
            for period in regime_periods:
                if period.regime == regime:
                    date_range = pd.date_range(period.start_date, period.end_date, freq='D')
                    regime_dates.extend(date_range)

            if not regime_dates:
                regime_alpha[regime.value] = 0.0
                continue

            # Filter benchmark returns for this regime
            regime_benchmark_mask = benchmark_returns.index.isin(regime_dates)
            regime_benchmark_returns = benchmark_returns[regime_benchmark_mask]

            perf = regime_performance[regime.value]

            if len(regime_benchmark_returns) == 0 or perf.total_trades == 0:
                regime_alpha[regime.value] = 0.0
                continue

            # Calculate benchmark performance
            benchmark_total_return = (1 + regime_benchmark_returns).prod() - 1

            # Alpha = strategy return - benchmark return (simplified)
            alpha = perf.total_return - benchmark_total_return

            # Risk-adjust alpha (subtract benchmark volatility-adjusted return)
            benchmark_volatility = regime_benchmark_returns.std() * np.sqrt(252)
            benchmark_sharpe = (regime_benchmark_returns.mean() / benchmark_volatility * np.sqrt(252)
                              if benchmark_volatility > 0 else 0.0)

            # Risk-adjusted alpha
            risk_adjusted_alpha = perf.sharpe_ratio - benchmark_sharpe

            regime_alpha[regime.value] = risk_adjusted_alpha

        return regime_alpha

    def _create_empty_result(self) -> RegimeValidationResult:
        """Create empty result for failed validation."""
        empty_performance = PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, volatility=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
            calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
            total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
        )

        return RegimeValidationResult(
            overall_performance=empty_performance,
            regime_performance={regime.value: empty_performance for regime in MarketRegime},
            regime_distribution={regime.value: 0.0 for regime in MarketRegime},
            regime_transitions={
                from_regime.value: {to_regime.value: 0 for to_regime in MarketRegime}
                for from_regime in MarketRegime
            },
            regime_stability_score=0.0,
            regime_adaptability_score=0.0,
            best_regime="",
            worst_regime="",
            regime_risk_adjusted_alpha={regime.value: 0.0 for regime in MarketRegime}
        )
