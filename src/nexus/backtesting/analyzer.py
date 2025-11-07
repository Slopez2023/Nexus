"""Performance analysis and metrics calculation.

Comprehensive performance measurement with statistical rigor,
risk metrics, and professional reporting.
"""

from typing import List, Dict, Any, Optional
import logging

import numpy as np
import pandas as pd
from scipy import stats

from .models import (
    PortfolioState, Trade, PerformanceMetrics, SignificanceTest,
    calculate_returns, calculate_max_drawdown, calculate_sharpe_ratio,
    calculate_sortino_ratio, calculate_win_rate, calculate_profit_factor
)

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Professional performance analysis with statistical rigor.

    Calculates comprehensive performance metrics including:
    - Return metrics (total, annualized, volatility)
    - Risk metrics (Sharpe, Sortino, VaR, CVaR)
    - Trade analysis (win rate, profit factor, expectancy)
    - Drawdown analysis (max DD, DD duration, recovery)
    - Statistical significance testing
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize analyzer.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculations
        """
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(self, portfolio_states: List[PortfolioState],
                         trades: List[Trade]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics.

        Args:
            portfolio_states: Complete portfolio history
            trades: All executed trades

        Returns:
            PerformanceMetrics: Complete performance analysis
        """
        if not portfolio_states:
            raise ValueError("No portfolio states provided")

        # Basic return calculations
        equity_curve = self._calculate_equity_curve(portfolio_states)
        returns = calculate_returns(portfolio_states)

        if len(returns) == 0:
            # Handle case with insufficient data
            return PerformanceMetrics(
                total_return=0.0,
                annualized_return=0.0,
                volatility=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                calmar_ratio=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                avg_trade_pnl=0.0,
                best_trade=0.0,
                worst_trade=0.0
            )

        # Time period in years
        days = (portfolio_states[-1].timestamp - portfolio_states[0].timestamp).days
        years = days / 365.25

        # Return metrics
        total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
        volatility = returns.std() * np.sqrt(252)  # Annualized

        # Risk-adjusted metrics
        sharpe_ratio = calculate_sharpe_ratio(returns, self.risk_free_rate)
        sortino_ratio = calculate_sortino_ratio(returns, self.risk_free_rate)

        # Drawdown metrics
        max_drawdown = calculate_max_drawdown(portfolio_states)
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0

        # Trade metrics
        win_rate = calculate_win_rate(returns)
        profit_factor = calculate_profit_factor(returns)

        # Individual trade analysis
        trade_returns = [trade.net_amount for trade in trades]
        total_trades = len(trade_returns)
        avg_trade_pnl = sum(trade_returns) / total_trades if total_trades > 0 else 0.0
        best_trade = max(trade_returns) if trade_returns else 0.0
        worst_trade = min(trade_returns) if trade_returns else 0.0

        # Confidence intervals (simplified bootstrap)
        sharpe_ci = self._calculate_confidence_interval(
            lambda: calculate_sharpe_ratio(self._bootstrap_sample(returns), self.risk_free_rate),
            returns, n_boot=1000
        )

        return_ci = self._calculate_confidence_interval(
            lambda: self._bootstrap_sample(returns).mean(),
            returns, n_boot=1000
        )

        metrics = PerformanceMetrics(
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
            worst_trade=worst_trade,
            sharpe_ci_lower=sharpe_ci[0],
            sharpe_ci_upper=sharpe_ci[1],
            return_ci_lower=return_ci[0] * 252,  # Annualized
            return_ci_upper=return_ci[1] * 252   # Annualized
        )

        logger.info(f"Calculated performance metrics: return={total_return:.2%}, "
                   f"sharpe={sharpe_ratio:.2f}, max_dd={max_drawdown:.2%}")

        return metrics

    def _calculate_equity_curve(self, portfolio_states: List[PortfolioState]) -> pd.Series:
        """Calculate equity curve from portfolio states."""
        values = [state.total_value for state in portfolio_states]
        dates = [state.timestamp for state in portfolio_states]
        return pd.Series(values, index=dates)

    def _bootstrap_sample(self, data: pd.Series, n_boot: int = 1000) -> pd.Series:
        """Generate bootstrap sample from data."""
        return data.sample(n=len(data), replace=True, random_state=np.random.randint(10000))

    def _calculate_confidence_interval(self, statistic_func, data: pd.Series,
                                    n_boot: int = 1000, alpha: float = 0.05) -> tuple[float, float]:
        """Calculate confidence interval using bootstrap."""
        if len(data) < 10:  # Insufficient data
            return (0.0, 0.0)

        bootstrap_stats = []
        for _ in range(n_boot):
            sample = self._bootstrap_sample(data)
            try:
                stat = statistic_func()
                bootstrap_stats.append(stat)
            except:
                continue

        if not bootstrap_stats:
            return (0.0, 0.0)

        bootstrap_stats = np.array(bootstrap_stats)
        lower = np.percentile(bootstrap_stats, alpha * 100 / 2)
        upper = np.percentile(bootstrap_stats, 100 - alpha * 100 / 2)

        return (lower, upper)

    def test_significance(self, strategy_returns: pd.Series,
                         benchmark_returns: Optional[pd.Series] = None,
                         alpha: float = 0.05) -> SignificanceTest:
        """Test statistical significance of strategy performance.

        Args:
            strategy_returns: Strategy returns series
            benchmark_returns: Optional benchmark returns
            alpha: Significance level

        Returns:
            SignificanceTest: Statistical test results
        """
        if len(strategy_returns) < 30:  # Minimum sample size
            return SignificanceTest(
                p_value=1.0,
                test_statistic=0.0,
                confidence_level=1-alpha,
                is_significant=False,
                effect_size=0.0,
                sample_size=len(strategy_returns),
                test_type="insufficient_data"
            )

        # Test vs zero (no skill)
        t_stat, p_value = stats.ttest_1samp(strategy_returns.values, 0.0)

        # Effect size (Cohen's d)
        effect_size = strategy_returns.mean() / strategy_returns.std() if strategy_returns.std() > 0 else 0.0

        # Test vs benchmark if provided
        if benchmark_returns is not None and len(benchmark_returns) == len(strategy_returns):
            excess_returns = strategy_returns - benchmark_returns
            t_stat_bench, p_value_bench = stats.ttest_1samp(excess_returns.values, 0.0)

            # Use the more conservative p-value
            if p_value_bench < p_value:
                p_value = p_value_bench
                t_stat = t_stat_bench

        return SignificanceTest(
            p_value=p_value,
            test_statistic=t_stat,
            confidence_level=1-alpha,
            is_significant=p_value < alpha,
            effect_size=effect_size,
            sample_size=len(strategy_returns),
            test_type="t-test_vs_zero"
        )

    def analyze_drawdowns(self, portfolio_states: List[PortfolioState]) -> Dict[str, Any]:
        """Analyze drawdown characteristics.

        Args:
            portfolio_states: Portfolio history

        Returns:
            Dictionary with drawdown analysis
        """
        equity = self._calculate_equity_curve(portfolio_states)
        rolling_max = equity.expanding().max()
        drawdowns = (equity - rolling_max) / rolling_max

        # Find drawdown periods
        drawdown_periods = []
        in_drawdown = False
        start_date = None

        for date, dd in drawdowns.items():
            if dd < 0 and not in_drawdown:
                # Start of drawdown
                in_drawdown = True
                start_date = date
            elif dd >= 0 and in_drawdown:
                # End of drawdown
                end_date = date
                peak_date = rolling_max.loc[start_date:end_date].idxmax()
                recovery_date = date

                drawdown_periods.append({
                    'start_date': start_date,
                    'peak_date': peak_date,
                    'end_date': end_date,
                    'recovery_date': recovery_date,
                    'max_drawdown': drawdowns.loc[start_date:end_date].min(),
                    'duration_days': (end_date - start_date).days,
                    'recovery_days': (recovery_date - peak_date).days
                })

                in_drawdown = False
                start_date = None

        return {
            'max_drawdown': drawdowns.min(),
            'avg_drawdown': drawdowns[drawdowns < 0].mean() if any(drawdowns < 0) else 0.0,
            'drawdown_periods': len(drawdown_periods),
            'longest_drawdown_days': max((p['duration_days'] for p in drawdown_periods), default=0),
            'avg_recovery_days': np.mean([p['recovery_days'] for p in drawdown_periods]) if drawdown_periods else 0.0,
            'current_drawdown': drawdowns.iloc[-1] if drawdowns.iloc[-1] < 0 else 0.0
        }

    def calculate_risk_metrics(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate comprehensive risk metrics.

        Args:
            returns: Return series

        Returns:
            Dictionary of risk metrics
        """
        if len(returns) < 10:
            return {}

        # Value at Risk
        var_95 = returns.quantile(0.05)
        var_99 = returns.quantile(0.01)

        # Conditional VaR (Expected Shortfall)
        cvar_95 = returns[returns <= var_95].mean() if any(returns <= var_95) else var_95
        cvar_99 = returns[returns <= var_99].mean() if any(returns <= var_99) else var_99

        # Tail risk metrics
        skewness = returns.skew()
        kurtosis = returns.kurtosis()

        # Downside deviation
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() if len(downside_returns) > 0 else 0.0

        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'skewness': skewness,
            'kurtosis': kurtosis,
            'downside_deviation': downside_deviation,
            'worst_day': returns.min(),
            'best_day': returns.max(),
            'return_stdev': returns.std(),
            'return_skewness_adj': returns.mean() / downside_deviation if downside_deviation > 0 else 0.0
        }

    def generate_performance_report(self, metrics: PerformanceMetrics,
                                  drawdown_analysis: Dict[str, Any],
                                  risk_metrics: Dict[str, float]) -> str:
        """Generate human-readable performance report.

        Args:
            metrics: Performance metrics
            drawdown_analysis: Drawdown analysis
            risk_metrics: Risk metrics

        Returns:
            Formatted performance report
        """
        report = f"""
PERFORMANCE REPORT
==================

RETURN METRICS
--------------
Total Return: {metrics.total_return:.2%}
Annualized Return: {metrics.annualized_return:.2%}
Volatility: {metrics.volatility:.2%}

RISK METRICS
-------------
Sharpe Ratio: {metrics.sharpe_ratio:.2f}
Sortino Ratio: {metrics.sortino_ratio:.2f}
Maximum Drawdown: {metrics.max_drawdown:.2%}
Calmar Ratio: {metrics.calmar_ratio:.2f}

TRADE ANALYSIS
--------------
Total Trades: {metrics.total_trades}
Win Rate: {metrics.win_rate:.2%}
Profit Factor: {metrics.profit_factor:.2f}
Average Trade P&L: ${metrics.avg_trade_pnl:.2f}
Best Trade: ${metrics.best_trade:.2f}
Worst Trade: ${metrics.worst_trade:.2f}

DRAWDOWN ANALYSIS
-----------------
Average Drawdown: {drawdown_analysis['avg_drawdown']:.2%}
Number of Drawdown Periods: {drawdown_analysis['drawdown_periods']}
Longest Drawdown: {drawdown_analysis['longest_drawdown_days']} days
Average Recovery Time: {drawdown_analysis['avg_recovery_days']:.1f} days

RISK ANALYSIS
-------------
VaR (95%): {risk_metrics.get('var_95', 0):.2%}
CVaR (95%): {risk_metrics.get('cvar_95', 0):.2%}
Skewness: {risk_metrics.get('skewness', 0):.2f}
Kurtosis: {risk_metrics.get('kurtosis', 0):.2f}

SIGNIFICANCE TESTING
--------------------
Sharpe Ratio CI: [{metrics.sharpe_ci_lower:.2f}, {metrics.sharpe_ci_upper:.2f}]
Return CI: [{metrics.return_ci_lower:.2%}, {metrics.return_ci_upper:.2%}]
"""

        return report
