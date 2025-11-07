"""Walk-forward analysis for out-of-sample validation.

Implements rolling time window analysis with parameter optimization
in each training window and out-of-sample testing to detect overfitting
and assess strategy robustness.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import numpy as np
import pandas as pd
from scipy import optimize

from .models import (
    WalkForwardResult, BacktestResult, PerformanceMetrics,
    BacktestConfig, CostConfig, RiskLimits
)
from .analyzer import PerformanceAnalyzer
from .engine import BacktestEngine
from .validator import StatisticalValidator

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward window configuration."""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    window_id: int

    @property
    def train_days(self) -> int:
        """Training period length in days."""
        return (self.train_end - self.train_start).days

    @property
    def test_days(self) -> int:
        """Test period length in days."""
        return (self.test_end - self.test_start).days


@dataclass
class ParameterOptimization:
    """Parameter optimization results for a training window."""
    window_id: int
    optimal_params: Dict[str, Any]
    optimization_score: float
    parameter_bounds: Dict[str, Tuple[float, float]]
    optimization_method: str = "grid_search"


class WalkForwardAnalyzer:
    """Walk-forward analysis with rolling optimization and out-of-sample testing.

    Implements professional walk-forward validation:
    - Rolling time windows with expanding/rolling training periods
    - Parameter optimization in each training window
    - Out-of-sample performance tracking
    - Stability analysis across windows
    """

    def __init__(
        self,
        training_years: float = 2.0,
        testing_months: int = 6,
        step_months: int = 3,
        min_train_years: float = 1.0,
        optimization_metric: str = "sharpe_ratio",
        n_parameter_combinations: int = 50
    ):
        """Initialize walk-forward analyzer.

        Args:
            training_years: Length of training period in years
            testing_months: Length of testing period in months
            step_months: Step size between windows in months
            min_train_years: Minimum training period length
            optimization_metric: Metric to optimize parameters on
            n_parameter_combinations: Number of parameter combinations to test
        """
        self.training_years = training_years
        self.testing_months = testing_months
        self.step_months = step_months
        self.min_train_years = min_train_years
        self.optimization_metric = optimization_metric
        self.n_parameter_combinations = n_parameter_combinations

        self.engine = BacktestEngine()
        self.analyzer = PerformanceAnalyzer()
        self.validator = StatisticalValidator()

    def analyze(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        parameter_ranges: Dict[str, Tuple[float, float]],
        initial_capital: float = 100000.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> WalkForwardResult:
        """Run complete walk-forward analysis.

        Args:
            strategy_func: Strategy function that takes parameters and returns signals
            price_data: Historical price data with datetime index
            parameter_ranges: Parameter bounds for optimization
            initial_capital: Starting portfolio capital
            start_date: Analysis start date (optional)
            end_date: Analysis end date (optional)

        Returns:
            WalkForwardResult: Complete walk-forward analysis
        """
        # Set date range
        if start_date is None:
            start_date = price_data.index[0]
        if end_date is None:
            end_date = price_data.index[-1]

        # Generate walk-forward windows
        windows = self._generate_windows(start_date, end_date)

        logger.info(f"Generated {len(windows)} walk-forward windows")

        # Run analysis for each window
        window_results = []
        parameter_history = []

        for window in windows:
            logger.info(f"Processing window {window.window_id}: {window.train_start.date()} - {window.test_end.date()}")

            # Optimize parameters on training data
            optimal_params = self._optimize_parameters(
                strategy_func, price_data, window, parameter_ranges
            )

            # Run out-of-sample test
            test_result = self._run_window_test(
                strategy_func, price_data, window, optimal_params, initial_capital
            )

            window_results.append(test_result)
            parameter_history.append({
                'window_id': window.window_id,
                'params': optimal_params,
                'train_score': optimal_params.get('optimization_score', 0.0)
            })

        # Calculate overall out-of-sample performance
        oos_performance = self._calculate_combined_performance(window_results)

        # Calculate parameter stability
        stability_score = self._calculate_parameter_stability(parameter_history)

        # Prepare result
        result = WalkForwardResult(
            config=self._create_config(start_date, end_date, initial_capital),
            window_results=window_results,
            optimal_parameters={},  # Will be set to most stable parameters
            parameter_performance=self._extract_parameter_performance(parameter_history),
            stability_score=stability_score,
            out_of_sample_performance=oos_performance
        )

        logger.info(f"Walk-forward analysis complete. Stability score: {stability_score:.3f}")
        return result

    def _generate_windows(self, start_date: datetime, end_date: datetime) -> List[WalkForwardWindow]:
        """Generate walk-forward analysis windows.

        Args:
            start_date: Overall analysis start
            end_date: Overall analysis end

        Returns:
            List of WalkForwardWindow objects
        """
        windows = []
        window_id = 0

        current_train_end = start_date + timedelta(days=int(self.training_years * 365.25))

        while current_train_end + timedelta(days=int(self.testing_months * 30.44)) <= end_date:
            train_start = current_train_end - timedelta(days=int(self.training_years * 365.25))
            train_end = current_train_end
            test_start = current_train_end
            test_end = test_start + timedelta(days=int(self.testing_months * 30.44))

            # Ensure minimum training period
            if (train_end - train_start).days >= int(self.min_train_years * 365.25):
                windows.append(WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    window_id=window_id
                ))
                window_id += 1

            # Move to next window
            current_train_end += timedelta(days=int(self.step_months * 30.44))

        return windows

    def _optimize_parameters(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        window: WalkForwardWindow,
        parameter_ranges: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Any]:
        """Optimize strategy parameters on training data.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            window: Current window
            parameter_ranges: Parameter bounds

        Returns:
            Optimal parameters dictionary
        """
        # Generate parameter combinations
        param_combinations = self._generate_parameter_combinations(parameter_ranges)

        best_params = None
        best_score = float('-inf')

        # Test each parameter combination
        for params in param_combinations:
            try:
                # Run backtest on training data
                train_data = price_data[window.train_start:window.train_end]
                if len(train_data) < 30:  # Minimum data requirement
                    continue

                # Generate signals
                signals = strategy_func(train_data, **params)

                # Calculate training performance
                score = self._evaluate_parameter_combination(train_data, signals)

                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_params['optimization_score'] = score

            except Exception as e:
                logger.warning(f"Parameter combination failed: {params}, error: {e}")
                continue

        if best_params is None:
            # Fallback to midpoint of ranges
            best_params = {
                param: (min_val + max_val) / 2
                for param, (min_val, max_val) in parameter_ranges.items()
            }
            best_params['optimization_score'] = 0.0

        return best_params

    def _generate_parameter_combinations(self, parameter_ranges: Dict[str, Tuple[float, float]]) -> List[Dict[str, float]]:
        """Generate parameter combinations for optimization.

        Args:
            parameter_ranges: Parameter bounds

        Returns:
            List of parameter dictionaries
        """
        if not parameter_ranges:
            return [{}]

        # For simplicity, use random sampling from ranges
        combinations = []
        for _ in range(self.n_parameter_combinations):
            params = {}
            for param_name, (min_val, max_val) in parameter_ranges.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    params[param_name] = np.random.randint(min_val, max_val + 1)
                else:
                    params[param_name] = np.random.uniform(min_val, max_val)
            combinations.append(params)

        return combinations

    def _evaluate_parameter_combination(self, price_data: pd.Series, signals: pd.Series) -> float:
        """Evaluate a parameter combination on training data.

        Args:
            price_data: Training price data
            signals: Strategy signals

        Returns:
            Performance score
        """
        try:
            # Calculate returns
            returns = signals.shift(1) * price_data.pct_change()
            returns = returns.dropna()

            if len(returns) < 10:
                return float('-inf')

            # Calculate Sharpe ratio as optimization metric
            if self.optimization_metric == "sharpe_ratio":
                mean_return = returns.mean()
                std_return = returns.std()
                if std_return > 0:
                    score = (mean_return / std_return) * np.sqrt(252)  # Annualized
                else:
                    score = float('-inf')
            elif self.optimization_metric == "total_return":
                score = (1 + returns).prod() - 1
            elif self.optimization_metric == "win_rate":
                score = (returns > 0).mean()
            else:
                score = returns.mean() * 252  # Annualized return

            return score

        except Exception as e:
            logger.warning(f"Parameter evaluation failed: {e}")
            return float('-inf')

    def _run_window_test(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        window: WalkForwardWindow,
        params: Dict[str, Any],
        initial_capital: float
    ) -> BacktestResult:
        """Run out-of-sample test for a window.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            window: Current window
            params: Optimal parameters
            initial_capital: Starting capital

        Returns:
            BacktestResult for the test period
        """
        try:
            # Get test data
            test_data = price_data[window.test_start:window.test_end]

            # Generate signals for test period
            signals = strategy_func(test_data, **{k: v for k, v in params.items() if k != 'optimization_score'})

            # Create minimal backtest config for test period
            config = BacktestConfig(
                initial_capital=initial_capital,
                start_date=window.test_start,
                end_date=window.test_end,
                transaction_costs=CostConfig(),
                risk_limits=RiskLimits()
            )

            # Run simplified backtest (could be enhanced to use full engine)
            portfolio_states, trades = self._run_simplified_backtest(
                test_data, signals, config
            )

            # Calculate performance
            performance = self.analyzer.calculate_metrics(portfolio_states, trades)

            # Create result
            result = BacktestResult(
                config=config,
                portfolio_states=portfolio_states,
                trades=trades,
                performance=performance,
                significance_tests=[],  # Could add significance testing
                equity_curve=pd.Series([s.total_value for s in portfolio_states],
                                     index=[s.timestamp for s in portfolio_states]),
                drawdowns=pd.Series(),  # Could calculate
                monthly_returns=pd.Series(),  # Could calculate
                risk_metrics={},
                execution_time=0.0,
                data_quality_score=1.0,
                warnings=[]
            )

            return result

        except Exception as e:
            logger.error(f"Window test failed for window {window.window_id}: {e}")
            # Return empty result
            return self._create_empty_result(window, initial_capital)

    def _run_simplified_backtest(
        self,
        price_data: pd.Series,
        signals: pd.Series,
        config: BacktestConfig
    ) -> Tuple[List[Any], List[Any]]:
        """Run simplified backtest for walk-forward testing.

        Args:
            price_data: Price data
            signals: Trading signals
            config: Backtest configuration

        Returns:
            Tuple of (portfolio_states, trades)
        """
        # Simplified backtest - could be enhanced
        capital = config.initial_capital
        position = 0
        portfolio_states = []
        trades = []

        for date, price in price_data.items():
            signal = signals.get(date, 0)

            # Simple position sizing
            if signal == 1 and position == 0:
                # Buy
                shares = capital // price
                cost = shares * price
                capital -= cost
                position = shares
                trades.append(type('Trade', (), {
                    'timestamp': date,
                    'symbol': 'ASSET',
                    'side': 'BUY',
                    'quantity': shares,
                    'price': price,
                    'commission': 0.0,
                    'slippage': 0.0,
                    'total_cost': cost,
                    'net_amount': -cost
                })())

            elif signal == -1 and position > 0:
                # Sell
                proceeds = position * price
                capital += proceeds
                trades.append(type('Trade', (), {
                    'timestamp': date,
                    'symbol': 'ASSET',
                    'side': 'SELL',
                    'quantity': position,
                    'price': price,
                    'commission': 0.0,
                    'slippage': 0.0,
                    'total_cost': 0.0,
                    'net_amount': proceeds
                })())
                position = 0

            # Create portfolio state
            portfolio_value = capital + position * price
            portfolio_states.append(type('PortfolioState', (), {
                'timestamp': date,
                'cash': capital,
                'positions': {'ASSET': type('Position', (), {
                    'symbol': 'ASSET',
                    'quantity': position,
                    'average_price': price,
                    'market_value': position * price,
                    'unrealized_pnl': 0.0
                })()},
                'total_value': portfolio_value,
                'daily_return': 0.0
            })())

        return portfolio_states, trades

    def _create_empty_result(self, window: WalkForwardWindow, initial_capital: float) -> BacktestResult:
        """Create empty backtest result for failed windows."""
        config = BacktestConfig(
            initial_capital=initial_capital,
            start_date=window.test_start,
            end_date=window.test_end,
            transaction_costs=CostConfig(),
            risk_limits=RiskLimits()
        )

        return BacktestResult(
            config=config,
            portfolio_states=[],
            trades=[],
            performance=PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            ),
            significance_tests=[],
            equity_curve=pd.Series(),
            drawdowns=pd.Series(),
            monthly_returns=pd.Series(),
            risk_metrics={},
            execution_time=0.0,
            data_quality_score=0.0,
            warnings=["Backtest failed"]
        )

    def _calculate_combined_performance(self, window_results: List[BacktestResult]) -> PerformanceMetrics:
        """Calculate combined out-of-sample performance across all windows.

        Args:
            window_results: List of window backtest results

        Returns:
            Combined performance metrics
        """
        if not window_results:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        # Combine equity curves
        all_equity_curves = []
        all_returns = []

        for result in window_results:
            if not result.equity_curve.empty:
                all_equity_curves.append(result.equity_curve)

        if not all_equity_curves:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
                total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
            )

        # Simple combination - could be enhanced with more sophisticated methods
        combined_equity = pd.concat(all_equity_curves).sort_index()
        combined_returns = combined_equity.pct_change().dropna()

        # Calculate metrics
        total_return = combined_equity.iloc[-1] / combined_equity.iloc[0] - 1
        days = (combined_equity.index[-1] - combined_equity.index[0]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
        volatility = combined_returns.std() * np.sqrt(252)

        sharpe_ratio = combined_returns.mean() / combined_returns.std() * np.sqrt(252) if combined_returns.std() > 0 else 0.0
        sortino_ratio = self._calculate_sortino_ratio(combined_returns)

        # Max drawdown
        rolling_max = combined_equity.expanding().max()
        drawdowns = (combined_equity - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())

        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        win_rate = (combined_returns > 0).mean()
        profit_factor = self._calculate_profit_factor(combined_returns)

        # Trade metrics (simplified)
        total_trades = sum(len(result.trades) for result in window_results)
        avg_trade_pnl = combined_returns.mean()
        best_trade = combined_returns.max()
        worst_trade = combined_returns.min()

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
            total_trades=total_trades,
            avg_trade_pnl=avg_trade_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade
        )

    def _calculate_sortino_ratio(self, returns: pd.Series) -> float:
        """Calculate Sortino ratio."""
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        return returns.mean() / downside_returns.std() * np.sqrt(252)

    def _calculate_profit_factor(self, returns: pd.Series) -> float:
        """Calculate profit factor."""
        gross_profits = returns[returns > 0].sum()
        gross_losses = abs(returns[returns < 0].sum())
        return gross_profits / gross_losses if gross_losses > 0 else float('inf')

    def _calculate_parameter_stability(self, parameter_history: List[Dict]) -> float:
        """Calculate parameter stability across windows.

        Args:
            parameter_history: List of parameter sets from each window

        Returns:
            Stability score (0-1, higher is more stable)
        """
        if len(parameter_history) < 2:
            return 0.0

        # Extract parameter values
        param_names = set()
        for hist in parameter_history:
            param_names.update(hist['params'].keys())

        param_names.discard('optimization_score')  # Remove score

        if not param_names:
            return 1.0  # No parameters to vary

        stability_scores = []

        for param_name in param_names:
            values = []
            for hist in parameter_history:
                if param_name in hist['params']:
                    values.append(hist['params'][param_name])

            if len(values) >= 2:
                # Calculate coefficient of variation
                mean_val = np.mean(values)
                std_val = np.std(values)
                cv = std_val / abs(mean_val) if mean_val != 0 else float('inf')

                # Convert to stability score (lower CV = higher stability)
                stability = 1 / (1 + cv) if cv != float('inf') else 0.0
                stability_scores.append(stability)

        # Average stability across parameters
        return np.mean(stability_scores) if stability_scores else 0.0

    def _extract_parameter_performance(self, parameter_history: List[Dict]) -> Dict[str, List[float]]:
        """Extract parameter performance history.

        Args:
            parameter_history: Parameter history

        Returns:
            Dictionary of parameter performance by name
        """
        param_performance = {}

        for hist in parameter_history:
            for param_name, param_value in hist['params'].items():
                if param_name not in param_performance:
                    param_performance[param_name] = []
                param_performance[param_name].append(param_value)

        return param_performance

    def _create_config(self, start_date: datetime, end_date: datetime, initial_capital: float) -> BacktestConfig:
        """Create backtest configuration."""
        return BacktestConfig(
            initial_capital=initial_capital,
            start_date=start_date,
            end_date=end_date,
            transaction_costs=CostConfig(),
            risk_limits=RiskLimits()
        )
