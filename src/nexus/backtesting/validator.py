"""Statistical validation for backtesting results.

Implements rigorous statistical testing to determine if strategy
performance is statistically significant and not due to random chance.
"""

from typing import List, Optional, Dict, Any
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy import stats

from .models import SignificanceTest, PerformanceMetrics, MonteCarloResult
from .analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


class StatisticalValidator:
    """Rigorous statistical validation of backtesting results.

    Implements multiple testing correction, significance testing,
    and Monte Carlo robustness analysis to ensure strategy
    performance is statistically meaningful.
    """

    def __init__(self, confidence_level: float = 0.95, min_sample_size: int = 100):
        """Initialize validator.

        Args:
            confidence_level: Statistical confidence level (0.95 = 95%)
            min_sample_size: Minimum sample size for reliable statistics
        """
        self.confidence_level = confidence_level
        self.min_sample_size = min_sample_size
        self.alpha = 1 - confidence_level

    def test_strategy_significance(self, strategy_returns: pd.Series,
                                 benchmark_returns: Optional[pd.Series] = None) -> SignificanceTest:
        """Test if strategy returns are statistically significant.

        Args:
            strategy_returns: Daily returns of the strategy
            benchmark_returns: Optional benchmark returns for comparison

        Returns:
            SignificanceTest: Complete statistical test results
        """
        n = len(strategy_returns)

        # Check minimum sample size
        if n < self.min_sample_size:
            return SignificanceTest(
                p_value=1.0,
                test_statistic=0.0,
                confidence_level=self.confidence_level,
                is_significant=False,
                effect_size=0.0,
                sample_size=n,
                test_type="insufficient_sample"
            )

        # Test vs zero (no skill null hypothesis)
        test_returns = strategy_returns

        # If benchmark provided, test excess returns
        if benchmark_returns is not None and len(benchmark_returns) == n:
            test_returns = strategy_returns - benchmark_returns

        # t-test: H0 = mean return = 0
        t_stat, p_value = stats.ttest_1samp(test_returns.values, 0.0)

        # Effect size (Cohen's d for returns)
        effect_size = test_returns.mean() / test_returns.std() if test_returns.std() > 0 else 0.0

        # Sharpe ratio test (more appropriate for financial returns)
        sharpe_ratio = test_returns.mean() / test_returns.std() * np.sqrt(252) if test_returns.std() > 0 else 0.0

        # Test Sharpe ratio significance (simplified)
        if sharpe_ratio > 0:
            # Approximation: Sharpe > 0.5 is generally significant for large samples
            sharpe_p_value = 2 * (1 - stats.norm.cdf(sharpe_ratio * np.sqrt(n/252)))
            if sharpe_p_value < p_value:
                p_value = sharpe_p_value

        test_type = "excess_returns_vs_benchmark" if benchmark_returns is not None else "returns_vs_zero"

        return SignificanceTest(
            p_value=p_value,
            test_statistic=t_stat,
            confidence_level=self.confidence_level,
            is_significant=p_value < self.alpha,
            effect_size=effect_size,
            sample_size=n,
            test_type=test_type
        )

    def multiple_testing_correction(self, p_values: List[float],
                                  method: str = 'bonferroni') -> List[float]:
        """Apply multiple hypothesis testing correction.

        Args:
            p_values: List of p-values to correct
            method: Correction method ('bonferroni', 'holm', 'benjamini-hochberg')

        Returns:
            List of corrected p-values
        """
        p_values = np.array(p_values)
        n = len(p_values)

        if method == 'bonferroni':
            return np.minimum(p_values * n, 1.0)

        elif method == 'holm':
            # Holm-Bonferroni correction
            sorted_indices = np.argsort(p_values)
            sorted_p = p_values[sorted_indices]
            corrected = np.ones(n)

            for i in range(n):
                corrected[sorted_indices[i]] = min(sorted_p[i] * (n - i), 1.0)

            return corrected

        elif method == 'benjamini-hochberg':
            # Benjamini-Hochberg FDR correction
            sorted_indices = np.argsort(p_values)
            sorted_p = p_values[sorted_indices]
            corrected = np.ones(n)

            for i in range(n):
                rank = i + 1
                corrected[sorted_indices[i]] = min(sorted_p[i] * n / rank, 1.0)

            return corrected

        else:
            raise ValueError(f"Unknown correction method: {method}")

    def _run_single_simulation(self, strategy_returns: pd.Series, seed: int) -> Dict[str, float]:
        """Run a single Monte Carlo simulation iteration."""
        np.random.seed(seed)
        sample = strategy_returns.sample(n=len(strategy_returns), replace=True)

        # Calculate metrics
        total_return = (1 + sample).prod() - 1
        sharpe = sample.mean() / sample.std() * np.sqrt(252) if sample.std() > 0 else 0.0

        # Max drawdown
        cum_returns = (1 + sample).cumprod()
        rolling_max = cum_returns.expanding().max()
        drawdowns = (cum_returns - rolling_max) / rolling_max
        max_dd = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd
        }

    def monte_carlo_simulation(self, strategy_returns: pd.Series,
                              n_simulations: int = 10000) -> MonteCarloResult:
        """Monte Carlo robustness testing.

        Args:
            strategy_returns: Strategy return series
            n_simulations: Number of Monte Carlo simulations

        Returns:
            MonteCarloResult: Complete Monte Carlo analysis
        """
        if len(strategy_returns) < 30:
            # Insufficient data
            return MonteCarloResult(
                n_simulations=0,
                return_distribution=np.array([]),
                sharpe_distribution=np.array([]),
                max_drawdown_distribution=np.array([]),
                failure_rate=1.0,
                var_95=0.0,
                cvar_95=0.0,
                confidence_intervals={}
            )

        np.random.seed(42)  # Base seed for reproducible results

        # Use parallel processing for performance
        max_workers = min(8, n_simulations)  # Limit workers to avoid overhead
        return_dist = []
        sharpe_dist = []
        max_dd_dist = []

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all simulation tasks
            futures = [
                executor.submit(self._run_single_simulation, strategy_returns, seed)
                for seed in range(42, 42 + n_simulations)
            ]

            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                return_dist.append(result['total_return'])
                sharpe_dist.append(result['sharpe_ratio'])
                max_dd_dist.append(result['max_drawdown'])

        # Convert to numpy arrays
        return_dist = np.array(return_dist)
        sharpe_dist = np.array(sharpe_dist)
        max_dd_dist = np.array(max_dd_dist)

        # Calculate statistics
        failure_rate = np.mean(return_dist <= 0)  # Percentage with negative returns

        # Risk metrics
        var_95 = np.percentile(return_dist, 5)  # 5th percentile = 95% VaR
        cvar_95 = return_dist[return_dist <= var_95].mean() if np.any(return_dist <= var_95) else var_95

        # Enhanced confidence intervals at multiple levels
        confidence_levels = [0.90, 0.95, 0.99]
        confidence_intervals = {}

        for level in confidence_levels:
            ci_lower = (1 - level) / 2
            ci_upper = 1 - ci_lower
            level_key = f"{int(level * 100)}_ci"

            confidence_intervals[level_key] = {
                'return': (np.percentile(return_dist, ci_lower * 100),
                          np.percentile(return_dist, ci_upper * 100)),
                'sharpe': (np.percentile(sharpe_dist, ci_lower * 100),
                          np.percentile(sharpe_dist, ci_upper * 100)),
                'max_drawdown': (np.percentile(max_dd_dist, ci_lower * 100),
                                np.percentile(max_dd_dist, ci_upper * 100))
            }

        # Standard 95% CI for backward compatibility
        confidence_intervals['return'] = confidence_intervals['95_ci']['return']
        confidence_intervals['sharpe'] = confidence_intervals['95_ci']['sharpe']
        confidence_intervals['max_drawdown'] = confidence_intervals['95_ci']['max_drawdown']

        return MonteCarloResult(
            n_simulations=n_simulations,
            return_distribution=return_dist,
            sharpe_distribution=sharpe_dist,
            max_drawdown_distribution=max_dd_dist,
            failure_rate=failure_rate,
            var_95=var_95,
            cvar_95=cvar_95,
            confidence_intervals=confidence_intervals
        )

    def test_parameter_stability(self, parameter_values: List[float],
                               performance_values: List[float]) -> Dict[str, Any]:
        """Test if parameter values are stable across different performance levels.

        Args:
            parameter_values: List of parameter values used
            performance_values: Corresponding performance metrics

        Returns:
            Dictionary with stability analysis
        """
        if len(parameter_values) < 10:
            return {"stable": False, "reason": "insufficient_data"}

        # Correlation between parameters and performance
        corr_coef, p_value = stats.pearsonr(parameter_values, performance_values)

        # Test if correlation is significant
        is_stable = p_value > 0.05  # No significant correlation = stable

        return {
            "stable": is_stable,
            "correlation": corr_coef,
            "p_value": p_value,
            "parameter_range": max(parameter_values) - min(parameter_values),
            "optimal_parameter": parameter_values[np.argmax(performance_values)]
        }

    def calculate_minimum_sample_size(self, effect_size: float = 0.5,
                                    power: float = 0.8) -> int:
        """Calculate minimum sample size needed for statistical significance.

        Args:
            effect_size: Expected effect size (Cohen's d)
            power: Statistical power (1 - β)

        Returns:
            Minimum sample size required
        """
        # Cohen's d effect size for t-test
        # Power analysis formula
        z_alpha = stats.norm.ppf(1 - self.alpha / 2)  # Two-tailed
        z_beta = stats.norm.ppf(power)

        n = ((z_alpha + z_beta) / effect_size) ** 2

        return int(np.ceil(n))

    def validate_backtest_result(self, performance: PerformanceMetrics,
                               returns: pd.Series) -> Dict[str, Any]:
        """Comprehensive validation of backtest results.

        Args:
            performance: Performance metrics
            returns: Return series

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "overall_valid": True,
            "issues": [],
            "warnings": [],
            "recommendations": []
        }

        # Minimum sample size check
        min_samples = self.calculate_minimum_sample_size()
        if len(returns) < min_samples:
            validation_results["issues"].append(f"Insufficient sample size: {len(returns)} < {min_samples}")
            validation_results["overall_valid"] = False

        # Sharpe ratio significance
        if performance.sharpe_ratio < 0.5:
            validation_results["warnings"].append("Sharpe ratio below 0.5 suggests poor risk-adjusted returns")

        # Maximum drawdown check
        if performance.max_drawdown > 0.3:  # 30% max drawdown
            validation_results["issues"].append(".1%")
            validation_results["overall_valid"] = False

        # Win rate check
        if performance.win_rate < 0.4:
            validation_results["warnings"].append("Win rate below 40% suggests inconsistent strategy")

        # Profit factor check
        if performance.profit_factor < 1.2:
            validation_results["warnings"].append("Profit factor below 1.2 suggests insufficient edge")

        # Statistical significance
        significance_test = self.test_strategy_significance(returns)
        if not significance_test.is_significant:
            validation_results["issues"].append(f"Strategy not statistically significant (p={significance_test.p_value:.3f})")
            validation_results["overall_valid"] = False

        # Monte Carlo robustness (simplified check)
        if len(returns) >= 100:
            mc_result = self.monte_carlo_simulation(returns, n_simulations=100)
            if mc_result.failure_rate > 0.4:  # More than 40% negative returns
                validation_results["issues"].append(".1%")
                validation_results["overall_valid"] = False

        # Generate recommendations
        if not validation_results["overall_valid"]:
            validation_results["recommendations"].append("Strategy fails basic validation criteria - consider redesign")

        if validation_results["warnings"]:
            validation_results["recommendations"].append("Address warning conditions before live deployment")

        if validation_results["overall_valid"]:
            validation_results["recommendations"].append("Strategy passes basic validation - proceed to walk-forward testing")

        return validation_results
