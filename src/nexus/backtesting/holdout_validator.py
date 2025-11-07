"""Holdout validation for overfitting detection.

Implements strict train/test splits with unseen data validation
to detect overfitting and assess strategy generalization.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import pandas as pd
import numpy as np

from .validator import StatisticalValidator
from .analyzer import PerformanceAnalyzer
from .models import PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class HoldoutPeriod:
    """Single holdout validation period."""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    period_id: str
    description: str


@dataclass
class HoldoutValidationResult:
    """Results of holdout validation."""
    overall_train_performance: PerformanceMetrics
    overall_test_performance: PerformanceMetrics
    overfitting_score: float  # Measure of overfitting (0-1, higher = more overfitting)
    generalization_score: float  # Ability to generalize (0-1, higher = better)
    train_test_decay: float  # Performance decay from train to test
    stability_score: float  # Consistency across holdout periods
    holdout_periods: List[HoldoutPeriod]
    period_results: List[Dict[str, Any]]  # Results for each period
    overfitting_detected: bool
    confidence_level: float  # Statistical confidence in results


class HoldoutValidator:
    """Holdout validation for overfitting detection.

    Implements multiple validation techniques:
    - Temporal splits (pre-2020 vs 2020-2023)
    - Rolling holdout periods
    - Overfitting detection metrics
    - Generalization assessment
    """

    def __init__(
        self,
        holdout_date: datetime = datetime(2020, 1, 1),
        n_rolling_periods: int = 5,
        min_train_years: float = 2.0,
        confidence_level: float = 0.95
    ):
        """Initialize holdout validator.

        Args:
            holdout_date: Primary split date (e.g., 2020-01-01)
            n_rolling_periods: Number of rolling holdout periods
            min_train_years: Minimum training period length
            confidence_level: Statistical confidence level
        """
        self.holdout_date = holdout_date
        self.n_rolling_periods = n_rolling_periods
        self.min_train_years = min_train_years
        self.confidence_level = confidence_level

        self.statistical_validator = StatisticalValidator(confidence_level=confidence_level)
        self.performance_analyzer = PerformanceAnalyzer()

    def validate_strategy_holdout(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        parameter_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> HoldoutValidationResult:
        """Perform comprehensive holdout validation.

        Args:
            strategy_func: Strategy function
            price_data: Historical price data
            parameter_ranges: Parameter ranges for optimization (optional)
            strategy_params: Fixed strategy parameters (optional)

        Returns:
            HoldoutValidationResult: Complete holdout analysis
        """
        logger.info("Starting holdout validation")

        # Generate holdout periods
        holdout_periods = self._generate_holdout_periods(price_data)

        if not holdout_periods:
            logger.warning("No valid holdout periods generated")
            return self._create_empty_result()

        logger.info(f"Generated {len(holdout_periods)} holdout periods")

        # Run validation for each period
        period_results = []
        train_performances = []
        test_performances = []

        for period in holdout_periods:
            logger.info(f"Testing period: {period.description}")

            period_result = self._validate_single_period(
                strategy_func, price_data, period,
                parameter_ranges, strategy_params
            )

            period_results.append(period_result)
            train_performances.append(period_result['train_performance'])
            test_performances.append(period_result['test_performance'])

        # Calculate overall metrics
        overall_train_performance = self._calculate_overall_performance(train_performances)
        overall_test_performance = self._calculate_overall_performance(test_performances)

        # Calculate overfitting metrics
        overfitting_score = self._calculate_overfitting_score(
            train_performances, test_performances
        )

        generalization_score = 1.0 - overfitting_score  # Inverse relationship

        train_test_decay = self._calculate_train_test_decay(
            overall_train_performance, overall_test_performance
        )

        stability_score = self._calculate_stability_score(test_performances)

        # Detect overfitting
        overfitting_detected = self._detect_overfitting(
            overfitting_score, train_test_decay, stability_score
        )

        result = HoldoutValidationResult(
            overall_train_performance=overall_train_performance,
            overall_test_performance=overall_test_performance,
            overfitting_score=overfitting_score,
            generalization_score=generalization_score,
            train_test_decay=train_test_decay,
            stability_score=stability_score,
            holdout_periods=holdout_periods,
            period_results=period_results,
            overfitting_detected=overfitting_detected,
            confidence_level=self.confidence_level
        )

        logger.info(f"Holdout validation complete. Overfitting detected: {overfitting_detected}")
        return result

    def _generate_holdout_periods(self, price_data: pd.Series) -> List[HoldoutPeriod]:
        """Generate holdout validation periods.

        Args:
            price_data: Historical price data

        Returns:
            List of holdout periods
        """
        periods = []
        data_start = price_data.index[0]
        data_end = price_data.index[-1]

        # Primary holdout: pre-2020 vs 2020-2023
        if data_start < self.holdout_date < data_end:
            periods.append(HoldoutPeriod(
                train_start=data_start,
                train_end=self.holdout_date - timedelta(days=1),
                test_start=self.holdout_date,
                test_end=data_end,
                period_id="primary_2020_split",
                description="Pre-2020 vs 2020-2023"
            ))

        # Rolling holdout periods
        total_years = (data_end - data_start).days / 365.25

        if total_years >= self.min_train_years * 2:
            # Calculate period length for rolling windows
            test_years = max(0.5, total_years * 0.2)  # 20% for testing, min 6 months
            train_years = total_years - test_years

            step_years = (total_years - self.min_train_years) / self.n_rolling_periods

            for i in range(self.n_rolling_periods):
                train_end_offset = self.min_train_years + (i * step_years)
                train_end = data_start + timedelta(days=int(train_end_offset * 365.25))

                if train_end >= data_end:
                    break

                test_end = min(data_end, train_end + timedelta(days=int(test_years * 365.25)))

                periods.append(HoldoutPeriod(
                    train_start=data_start,
                    train_end=train_end,
                    test_start=train_end + timedelta(days=1),
                    test_end=test_end,
                    period_id=f"rolling_{i+1}",
                    description=f"Rolling period {i+1}: train until {train_end.date()}"
                ))

        return periods

    def _validate_single_period(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        period: HoldoutPeriod,
        parameter_ranges: Optional[Dict[str, Tuple[float, float]]],
        strategy_params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate strategy for a single holdout period.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            period: Holdout period
            parameter_ranges: Parameter ranges for optimization
            strategy_params: Fixed parameters

        Returns:
            Dictionary with period validation results
        """
        # Split data
        train_data = price_data[period.train_start:period.train_end]
        test_data = price_data[period.test_start:period.test_end]

        if len(train_data) < 30 or len(test_data) < 10:  # Minimum data requirements
            return self._create_failed_period_result(period)

        # Optimize parameters on training data (if ranges provided)
        if parameter_ranges and not strategy_params:
            optimal_params = self._optimize_parameters(strategy_func, train_data, parameter_ranges)
        else:
            optimal_params = strategy_params or {}

        # Generate signals for training period
        try:
            train_signals = strategy_func(train_data, **{k: v for k, v in optimal_params.items()
                                                        if k != 'optimization_score'})
            train_returns = self._calculate_strategy_returns(train_data, train_signals)
            train_performance = self._calculate_performance_metrics(train_returns)
        except Exception as e:
            logger.warning(f"Training period failed for {period.period_id}: {e}")
            train_performance = PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        # Generate signals for test period (out-of-sample)
        try:
            test_signals = strategy_func(test_data, **{k: v for k, v in optimal_params.items()
                                                      if k != 'optimization_score'})
            test_returns = self._calculate_strategy_returns(test_data, test_signals)
            test_performance = self._calculate_performance_metrics(test_returns)
        except Exception as e:
            logger.warning(f"Test period failed for {period.period_id}: {e}")
            test_performance = PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        return {
            'period_id': period.period_id,
            'description': period.description,
            'optimal_params': optimal_params,
            'train_performance': train_performance,
            'test_performance': test_performance,
            'train_test_ratio': (test_performance.sharpe_ratio / train_performance.sharpe_ratio
                               if train_performance.sharpe_ratio != 0 else 0.0),
            'performance_decay': train_performance.sharpe_ratio - test_performance.sharpe_ratio
        }

    def _optimize_parameters(
        self,
        strategy_func: Callable,
        train_data: pd.Series,
        parameter_ranges: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Any]:
        """Optimize strategy parameters on training data.

        Args:
            strategy_func: Strategy function
            train_data: Training data
            parameter_ranges: Parameter bounds

        Returns:
            Optimal parameters
        """
        # Simple grid search for demonstration (could be enhanced)
        n_combinations = min(20, 2 ** len(parameter_ranges))  # Limit combinations

        best_params = None
        best_score = float('-inf')

        for _ in range(n_combinations):
            params = {}
            for param_name, (min_val, max_val) in parameter_ranges.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    params[param_name] = np.random.randint(min_val, max_val + 1)
                else:
                    params[param_name] = np.random.uniform(min_val, max_val)

            try:
                signals = strategy_func(train_data, **params)
                returns = self._calculate_strategy_returns(train_data, signals)
                score = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0

                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_params['optimization_score'] = score

            except Exception as e:
                logger.debug(f"Parameter combination failed: {params}, error: {e}")
                continue

        if best_params is None:
            # Fallback to midpoints
            best_params = {
                param: (min_val + max_val) / 2
                for param, (min_val, max_val) in parameter_ranges.items()
            }
            best_params['optimization_score'] = 0.0

        return best_params

    def _calculate_strategy_returns(self, price_data: pd.Series, signals: pd.Series) -> pd.Series:
        """Calculate strategy returns from signals.

        Args:
            price_data: Price data
            signals: Trading signals (-1, 0, 1)

        Returns:
            Strategy returns series
        """
        # Simple long/short strategy
        returns = signals.shift(1) * price_data.pct_change()
        return returns.dropna()

    def _calculate_performance_metrics(self, returns: pd.Series) -> PerformanceMetrics:
        """Calculate performance metrics from returns.

        Args:
            returns: Strategy returns

        Returns:
            Performance metrics
        """
        if len(returns) == 0:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        total_return = (1 + returns).prod() - 1
        days = len(returns)
        years = days / 252
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
        volatility = returns.std() * np.sqrt(252)

        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)
                      if returns.std() > 0 else 0.0)

        downside_returns = returns[returns < 0]
        sortino_ratio = (returns.mean() / downside_returns.std() * np.sqrt(252)
                       if len(downside_returns) > 0 and downside_returns.std() > 0 else 0.0)

        # Max drawdown
        equity_curve = (1 + returns).cumprod()
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())

        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        win_rate = (returns > 0).mean()

        gross_profits = returns[returns > 0].sum()
        gross_losses = abs(returns[returns < 0].sum())
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
            total_trades=len(returns),
            avg_trade_pnl=returns.mean(),
            best_trade=returns.max(),
            worst_trade=returns.min()
        )

    def _calculate_overfitting_score(
        self,
        train_performances: List[PerformanceMetrics],
        test_performances: List[PerformanceMetrics]
    ) -> float:
        """Calculate overfitting score.

        Args:
            train_performances: Training period performances
            test_performances: Test period performances

        Returns:
            Overfitting score (0-1)
        """
        if len(train_performances) != len(test_performances):
            return 0.5  # Neutral score

        train_sharpes = [p.sharpe_ratio for p in train_performances if p.total_trades > 0]
        test_sharpes = [p.sharpe_ratio for p in test_performances if p.total_trades > 0]

        if not train_sharpes or not test_sharpes:
            return 0.5

        # Average performance decay
        decays = []
        for train_sharpe, test_sharpe in zip(train_sharpes, test_sharpes):
            if train_sharpe > 0:
                decay = max(0, (train_sharpe - test_sharpe) / train_sharpe)
                decays.append(decay)

        if not decays:
            return 0.0

        avg_decay = np.mean(decays)

        # Convert to overfitting score (0-1)
        # 0 = no overfitting, 1 = severe overfitting
        overfitting_score = min(1.0, avg_decay * 2)  # Scale for sensitivity

        return overfitting_score

    def _calculate_train_test_decay(
        self,
        overall_train: PerformanceMetrics,
        overall_test: PerformanceMetrics
    ) -> float:
        """Calculate train-test performance decay.

        Args:
            overall_train: Overall training performance
            overall_test: Overall test performance

        Returns:
            Performance decay ratio
        """
        if overall_train.sharpe_ratio == 0:
            return 1.0  # Complete decay

        decay = (overall_train.sharpe_ratio - overall_test.sharpe_ratio) / overall_train.sharpe_ratio
        return max(0.0, decay)  # Ensure non-negative

    def _calculate_stability_score(self, test_performances: List[PerformanceMetrics]) -> float:
        """Calculate stability score across holdout periods.

        Args:
            test_performances: Test period performances

        Returns:
            Stability score (0-1, higher = more stable)
        """
        sharpes = [p.sharpe_ratio for p in test_performances if p.total_trades > 0]

        if len(sharpes) < 2:
            return 0.0

        # Coefficient of variation
        mean_sharpe = np.mean(sharpes)
        std_sharpe = np.std(sharpes)

        if mean_sharpe == 0:
            return 0.0

        cv = std_sharpe / abs(mean_sharpe)

        # Convert to stability score
        stability = 1 / (1 + cv)

        return stability

    def _detect_overfitting(
        self,
        overfitting_score: float,
        train_test_decay: float,
        stability_score: float
    ) -> bool:
        """Detect if overfitting is present.

        Args:
            overfitting_score: Overfitting score
            train_test_decay: Train-test decay
            stability_score: Stability score

        Returns:
            True if overfitting detected
        """
        # Overfitting indicators
        high_overfitting = overfitting_score > 0.6  # Significant performance decay
        high_decay = train_test_decay > 0.5  # More than 50% performance loss
        low_stability = stability_score < 0.3  # Unstable across periods

        # Conservative overfitting detection
        overfitting_detected = high_overfitting and (high_decay or low_stability)

        return overfitting_detected

    def _calculate_overall_performance(self, performances: List[PerformanceMetrics]) -> PerformanceMetrics:
        """Calculate overall performance across periods.

        Args:
            performances: List of performance metrics

        Returns:
            Combined performance metrics
        """
        valid_performances = [p for p in performances if p.total_trades > 0]

        if not valid_performances:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        # Simple average of key metrics (could be enhanced with more sophisticated combination)
        avg_sharpe = np.mean([p.sharpe_ratio for p in valid_performances])
        avg_return = np.mean([p.total_return for p in valid_performances])
        avg_volatility = np.mean([p.volatility for p in valid_performances])
        avg_win_rate = np.mean([p.win_rate for p in valid_performances])

        # Use the worst metrics for risk measures (conservative approach)
        max_drawdown = max([p.max_drawdown for p in valid_performances])
        total_trades = sum([p.total_trades for p in valid_performances])

        return PerformanceMetrics(
            total_return=avg_return,
            annualized_return=avg_return,  # Approximation
            volatility=avg_volatility,
            sharpe_ratio=avg_sharpe,
            sortino_ratio=avg_sharpe,  # Approximation
            max_drawdown=max_drawdown,
            calmar_ratio=avg_return / max_drawdown if max_drawdown > 0 else 0.0,
            win_rate=avg_win_rate,
            profit_factor=1.5,  # Placeholder
            total_trades=total_trades,
            avg_trade_pnl=avg_return / total_trades if total_trades > 0 else 0.0,
            best_trade=0.0,  # Placeholder
            worst_trade=0.0   # Placeholder
        )

    def _create_empty_result(self) -> HoldoutValidationResult:
        """Create empty result for failed validation."""
        empty_performance = PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, volatility=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
            calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
            total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
        )

        return HoldoutValidationResult(
            overall_train_performance=empty_performance,
            overall_test_performance=empty_performance,
            overfitting_score=0.5,
            generalization_score=0.5,
            train_test_decay=0.0,
            stability_score=0.0,
            holdout_periods=[],
            period_results=[],
            overfitting_detected=False,
            confidence_level=self.confidence_level
        )

    def _create_failed_period_result(self, period: HoldoutPeriod) -> Dict[str, Any]:
        """Create failed period result."""
        empty_performance = PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, volatility=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
            calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
            total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
        )

        return {
            'period_id': period.period_id,
            'description': period.description,
            'optimal_params': {},
            'train_performance': empty_performance,
            'test_performance': empty_performance,
            'train_test_ratio': 0.0,
            'performance_decay': 0.0
        }
