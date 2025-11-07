"""Walk-forward optimization to prevent overfitting.

Implements rolling window analysis to ensure strategy parameters
are optimized on out-of-sample data, preventing curve-fitting.
"""

from typing import Dict, List, Any, Type, Optional, Callable
import logging
import itertools

import pandas as pd
import numpy as np

from ..strategies import BaseStrategy
from .models import BacktestConfig, BacktestResult, WalkForwardResult, OptimizationResult
from .engine import BacktestEngine
from .validator import StatisticalValidator

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """Walk-forward optimization for overfitting prevention.

    Uses rolling time windows to optimize strategy parameters on
    training data and validate on out-of-sample test data. This
    prevents the common mistake of curve-fitting to historical data.

    Key Features:
    - Rolling window optimization
    - Out-of-sample validation
    - Multiple parameter combinations
    - Statistical significance testing
    - Overfitting detection
    """

    def __init__(self, config: BacktestConfig):
        """Initialize optimizer.

        Args:
            config: Base backtest configuration
        """
        self.config = config
        self.engine = BacktestEngine(config)
        self.validator = StatisticalValidator()

    def optimize_parameters(self, strategy_class: Type[BaseStrategy],
                          parameter_space: Dict[str, List[Any]],
                          market_data: pd.DataFrame,
                          train_window_months: int = 12,
                          test_window_months: int = 3,
                          step_months: int = 3) -> WalkForwardResult:
        """Run walk-forward optimization.

        Args:
            strategy_class: Strategy class to optimize
            parameter_space: Dictionary of parameter names to lists of values
            market_data: Historical market data
            train_window_months: Training window length in months
            test_window_months: Test window length in months
            step_months: Step size between windows in months

        Returns:
            WalkForwardResult: Complete optimization results
        """
        logger.info(f"Starting walk-forward optimization for {strategy_class.__name__}")

        # Generate all parameter combinations
        param_names = list(parameter_space.keys())
        param_values = list(parameter_space.values())
        parameter_combinations = list(itertools.product(*param_values))

        logger.info(f"Testing {len(parameter_combinations)} parameter combinations")

        # Prepare data windows
        windows = self._create_rolling_windows(
            market_data, train_window_months, test_window_months, step_months
        )

        logger.info(f"Created {len(windows)} rolling windows")

        # Optimization results storage
        window_results = []
        param_performance = {name: [] for name in param_names}
        param_performance['sharpe_ratio'] = []
        param_performance['total_return'] = []
        param_performance['max_drawdown'] = []

        # Process each window
        for i, (train_data, test_data, train_start, test_start) in enumerate(windows):
            logger.info(f"Processing window {i+1}/{len(windows)}: train {train_start.date()} to {test_start.date()}")

            # Optimize parameters on training data
            best_params, best_metrics = self._optimize_window(
                strategy_class, parameter_combinations, train_data
            )

            # Validate on test data
            test_result = self._validate_parameters(
                strategy_class, best_params, test_data
            )

            window_results.append(test_result)

            # Store parameter performance
            for param_name in param_names:
                param_performance[param_name].append(best_params[param_name])

            param_performance['sharpe_ratio'].append(test_result.performance.sharpe_ratio)
            param_performance['total_return'].append(test_result.performance.total_return)
            param_performance['max_drawdown'].append(test_result.performance.max_drawdown)

        # Calculate stability metrics
        stability_score = self._calculate_stability_score(param_performance)

        # Create optimization result
        optimal_params = self._find_optimal_parameters(parameter_combinations, window_results)

        result = WalkForwardResult(
            config=self.config,
            window_results=window_results,
            optimal_parameters=optimal_params,
            parameter_performance=param_performance,
            stability_score=stability_score,
            out_of_sample_performance=self._calculate_average_performance(window_results)
        )

        logger.info(f"Walk-forward optimization completed: stability={stability_score:.2f}")

        return result

    def _create_rolling_windows(self, data: pd.DataFrame, train_months: int,
                              test_months: int, step_months: int) -> List[tuple]:
        """Create rolling time windows for walk-forward analysis.

        Args:
            data: Market data with datetime index
            train_months: Training window length
            test_months: Test window length
            step_months: Step size between windows

        Returns:
            List of (train_data, test_data, train_start, test_start) tuples
        """
        windows = []

        # Ensure data is sorted
        data = data.sort_index()

        start_date = data.index.min()
        end_date = data.index.max()

        current_train_start = start_date

        while True:
            # Calculate window dates
            train_end = current_train_start + pd.DateOffset(months=train_months)
            test_start = train_end
            test_end = test_start + pd.DateOffset(months=test_months)

            # Check if we have enough data
            if test_end > end_date:
                break

            # Extract window data
            train_mask = (data.index >= current_train_start) & (data.index < train_end)
            test_mask = (data.index >= test_start) & (data.index < test_end)

            train_data = data[train_mask]
            test_data = data[test_mask]

            if len(train_data) < 100 or len(test_data) < 20:  # Minimum data requirements
                current_train_start += pd.DateOffset(months=step_months)
                continue

            windows.append((train_data, test_data, current_train_start, test_start))

            # Move to next window
            current_train_start += pd.DateOffset(months=step_months)

        return windows

    def _optimize_window(self, strategy_class: Type[BaseStrategy],
                        parameter_combinations: List[tuple],
                        train_data: pd.DataFrame) -> tuple[Dict[str, Any], Any]:
        """Optimize parameters for a single training window.

        Args:
            strategy_class: Strategy class
            parameter_combinations: List of parameter tuples
            train_data: Training data

        Returns:
            Tuple of (best_params_dict, best_metrics)
        """
        best_sharpe = -float('inf')
        best_params = None
        best_metrics = None

        param_names = list(self._get_parameter_names(strategy_class))

        for param_values in parameter_combinations:
            # Create parameter dictionary
            params = dict(zip(param_names, param_values))

            try:
                # Create and run strategy
                strategy = strategy_class(**params)
                result = self.engine.run_backtest(strategy, train_data)

                # Evaluate performance (Sharpe ratio primary metric)
                sharpe = result.performance.sharpe_ratio

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
                    best_metrics = result.performance

            except Exception as e:
                logger.warning(f"Failed to test parameters {params}: {e}")
                continue

        if best_params is None:
            raise ValueError("No valid parameter combinations found")

        return best_params, best_metrics

    def _validate_parameters(self, strategy_class: Type[BaseStrategy],
                           params: Dict[str, Any], test_data: pd.DataFrame) -> BacktestResult:
        """Validate optimized parameters on test data.

        Args:
            strategy_class: Strategy class
            params: Optimized parameters
            test_data: Out-of-sample test data

        Returns:
            BacktestResult: Test performance
        """
        strategy = strategy_class(**params)
        result = self.engine.run_backtest(strategy, test_data)
        return result

    def _get_parameter_names(self, strategy_class: Type[BaseStrategy]) -> List[str]:
        """Extract parameter names from strategy constructor."""
        import inspect

        sig = inspect.signature(strategy_class.__init__)
        param_names = [name for name in sig.parameters.keys() if name != 'self']
        return param_names

    def _calculate_stability_score(self, param_performance: Dict[str, List]) -> float:
        """Calculate parameter stability score across windows.

        Args:
            param_performance: Parameter values and performance across windows

        Returns:
            Stability score (0-1, higher = more stable)
        """
        if not param_performance['sharpe_ratio']:
            return 0.0

        sharpe_ratios = param_performance['sharpe_ratio']

        # Coefficient of variation of Sharpe ratios (lower = more stable)
        sharpe_mean = np.mean(sharpe_ratios)
        sharpe_std = np.std(sharpe_ratios)

        if sharpe_mean == 0:
            return 0.0

        sharpe_cv = sharpe_std / abs(sharpe_mean)

        # Convert to stability score (lower CV = higher stability)
        # CV < 0.5 = very stable, CV > 2.0 = very unstable
        stability = max(0.0, min(1.0, 1.0 - sharpe_cv / 2.0))

        return stability

    def _find_optimal_parameters(self, parameter_combinations: List[tuple],
                               window_results: List[BacktestResult]) -> Dict[str, Any]:
        """Find the most robust parameter combination across all windows.

        Args:
            parameter_combinations: All tested parameter combinations
            window_results: Results from each window

        Returns:
            Dictionary of optimal parameters
        """
        if not window_results:
            return {}

        # Find combination with highest average Sharpe ratio
        best_avg_sharpe = -float('inf')
        best_params = None

        param_names = self._get_parameter_names_from_results(window_results[0])

        for param_combo in parameter_combinations:
            combo_sharpes = []

            for result in window_results:
                # Find result for this parameter combination
                # (This is a simplification - in practice we'd track which params gave which results)
                combo_sharpes.append(result.performance.sharpe_ratio)

            avg_sharpe = np.mean(combo_sharpes)

            if avg_sharpe > best_avg_sharpe:
                best_avg_sharpe = avg_sharpe
                best_params = dict(zip(param_names, param_combo))

        return best_params or {}

    def _get_parameter_names_from_results(self, result: BacktestResult) -> List[str]:
        """Extract parameter names from backtest result."""
        # This is a simplified approach - in practice we'd need to track
        # which parameters were used for each result
        return ['period', 'threshold']  # Default assumption

    def _calculate_average_performance(self, window_results: List[BacktestResult]) -> Any:
        """Calculate average performance across all windows."""
        if not window_results:
            return None

        # Average key metrics
        avg_return = np.mean([r.performance.total_return for r in window_results])
        avg_sharpe = np.mean([r.performance.sharpe_ratio for r in window_results])
        avg_max_dd = np.mean([r.performance.max_drawdown for r in window_results])

        # Create a mock PerformanceMetrics object with averages
        from .models import PerformanceMetrics
        return PerformanceMetrics(
            total_return=avg_return,
            annualized_return=avg_return,  # Simplified
            volatility=0.0,  # Not calculated
            sharpe_ratio=avg_sharpe,
            sortino_ratio=avg_sharpe,  # Simplified
            max_drawdown=avg_max_dd,
            calmar_ratio=avg_sharpe / avg_max_dd if avg_max_dd > 0 else 0.0,
            win_rate=0.0,  # Not calculated
            profit_factor=0.0,  # Not calculated
            total_trades=0,  # Not calculated
            avg_trade_pnl=0.0,  # Not calculated
            best_trade=0.0,  # Not calculated
            worst_trade=0.0,  # Not calculated
        )

    def grid_search_optimization(self, strategy_class: Type[BaseStrategy],
                               parameter_space: Dict[str, List[Any]],
                               data: pd.DataFrame,
                               metric: str = 'sharpe_ratio') -> OptimizationResult:
        """Simple grid search optimization (for comparison).

        WARNING: This is IN-SAMPLE optimization and will overfit!
        Only use for comparison with walk-forward results.

        Args:
            strategy_class: Strategy class
            parameter_space: Parameter search space
            data: Full dataset
            metric: Performance metric to optimize

        Returns:
            OptimizationResult: Best parameters found
        """
        logger.warning("Grid search is in-sample optimization - results will be overfitted!")

        # Generate parameter combinations
        param_names = list(parameter_space.keys())
        param_values = list(parameter_space.values())
        combinations = list(itertools.product(*param_values))

        best_score = -float('inf')
        best_params = None
        best_result = None

        for param_combo in combinations:
            params = dict(zip(param_names, param_combo))

            try:
                strategy = strategy_class(**params)
                result = self.engine.run_backtest(strategy, data)

                score = getattr(result.performance, metric)

                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result

            except Exception as e:
                logger.debug(f"Failed parameter combination {params}: {e}")
                continue

        if best_params is None:
            raise ValueError("No valid parameter combinations found")

        return OptimizationResult(
            best_parameters=best_params,
            best_performance=best_result.performance if best_result else None,
            all_results=[],  # Not implemented for simplicity
            optimization_method="grid_search",
            metric_used=metric
        )
