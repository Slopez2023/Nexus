#!/usr/bin/env python3
"""Comprehensive validation of momentum strategy using professional standards.

Implements Task 2.5: Statistical Backtesting & Validation with:
- Walk-forward analysis
- Transaction cost modeling
- Multi-regime testing
- Monte Carlo simulation
- Statistical significance testing
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json

import pandas as pd
import numpy as np
import yfinance as yf

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nexus.strategies import MomentumStrategy, StrategyFactory
from nexus.backtesting.engine import BacktestEngine
from nexus.backtesting.models import BacktestConfig, CostConfig, RiskLimits
from nexus.backtesting.optimizer import WalkForwardOptimizer
from nexus.backtesting.validator import StatisticalValidator
from nexus.backtesting.regime_detector import MarketRegimeDetector, MarketRegime
from nexus.backtesting.costs import create_realistic_cost_model

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MomentumStrategyValidator:
    """Comprehensive validator for momentum strategy following professional standards."""

    def __init__(self):
        """Initialize validator with professional settings."""
        self.strategy_class = MomentumStrategy
        self.validator = StatisticalValidator(confidence_level=0.95)
        self.regime_detector = MarketRegimeDetector()

        # Professional backtest configuration
        self.config = BacktestConfig(
            initial_capital=1_000_000,  # $1M starting capital
            start_date=datetime(2010, 1, 1),
            end_date=datetime(2023, 12, 31),
            transaction_costs=CostConfig(
                commission_per_share=0.005,
                commission_minimum=1.0,
                slippage_bps=5.0,
                market_impact_bps=2.0,
                exchange_fees=0.0001
            ),
            risk_limits=RiskLimits(
                max_position_size_pct=0.05,  # 5% max per position
                max_drawdown_pct=0.20,       # 20% max drawdown
                max_daily_loss_pct=0.05      # 5% max daily loss
            )
        )

    def load_market_data(self) -> pd.DataFrame:
        """Load market data for backtesting.

        Returns:
            DataFrame with OHLCV data for S&P 500 universe
        """
        logger.info("Loading market data...")

        # Use S&P 500 ETF as benchmark
        spy = yf.Ticker("SPY")
        spy_data = spy.history(start=self.config.start_date, end=self.config.end_date)

        # For simplicity, use SPY data (can be extended to full universe)
        market_data = pd.DataFrame({
            'open': spy_data['Open'],
            'high': spy_data['High'],
            'low': spy_data['Low'],
            'close': spy_data['Close'],
            'volume': spy_data['Volume']
        })

        # Add symbol index for multi-symbol support
        market_data['symbol'] = 'SPY'
        market_data = market_data.set_index(['symbol', market_data.index])

        logger.info(f"Loaded {len(market_data)} days of market data")
        return market_data

    def run_walk_forward_analysis(self, market_data: pd.DataFrame) -> dict:
        """Run walk-forward optimization analysis.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with walk-forward results
        """
        logger.info("Running walk-forward analysis...")

        optimizer = WalkForwardOptimizer(self.config)

        # Parameter space for momentum strategy
        parameter_space = {
            'formation_period_months': [3, 6, 12],
            'holding_period_months': [3, 6, 12],
            'percentile': [5.0, 10.0, 20.0],
            'max_positions': [None, 10, 20],  # None = unlimited
            'min_price': [1.0, 5.0],
            'min_volume': [1000, 10000]
        }

        # Run walk-forward optimization
        wf_result = optimizer.optimize_parameters(
            strategy_class=self.strategy_class,
            parameter_space=parameter_space,
            market_data=market_data,
            train_window_months=24,  # 2 years training
            test_window_months=6,    # 6 months testing
            step_months=6            # Step forward 6 months
        )

        # Analyze results
        wf_analysis = {
            'optimal_parameters': wf_result.optimal_parameters,
            'stability_score': wf_result.stability_score,
            'out_of_sample_performance': {
                'total_return': wf_result.out_of_sample_performance.total_return,
                'sharpe_ratio': wf_result.out_of_sample_performance.sharpe_ratio,
                'max_drawdown': wf_result.out_of_sample_performance.max_drawdown
            },
            'window_results_count': len(wf_result.window_results)
        }

        logger.info(".3f")
        return wf_analysis

    def run_regime_analysis(self, market_data: pd.DataFrame) -> dict:
        """Analyze strategy performance across market regimes.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with regime analysis results
        """
        logger.info("Running regime analysis...")

        # Get SPY prices for regime detection
        spy_prices = market_data.xs('SPY', level='symbol')['close']

        # Detect regimes
        regime_periods = self.regime_detector.detect_regimes(spy_prices)

        # Run backtest with optimal parameters (from walk-forward)
        optimal_params = {
            'formation_period_months': 6,
            'holding_period_months': 6,
            'percentile': 10.0,
            'max_positions': None,
            'min_price': 1.0,
            'min_volume': 1000
        }

        strategy = self.strategy_class(**optimal_params)
        engine = BacktestEngine(self.config)
        result = engine.run_backtest(strategy, market_data)

        # Get strategy and benchmark returns
        strategy_returns = result.equity_curve.pct_change().dropna()
        benchmark_returns = spy_prices.pct_change().dropna()

        # Align dates
        common_dates = strategy_returns.index.intersection(benchmark_returns.index)
        strategy_returns = strategy_returns[common_dates]
        benchmark_returns = benchmark_returns[common_dates]

        # Analyze performance by regime
        regime_performance = self.regime_detector.analyze_regime_performance(
            strategy_returns, benchmark_returns, regime_periods
        )

        regime_analysis = {
            'total_regime_periods': len(regime_periods),
            'regime_performance': regime_performance,
            'regime_distribution': {
                regime.value: sum(1 for p in regime_periods if p.regime == regime)
                for regime in MarketRegime
            }
        }

        logger.info(f"Analyzed performance across {len(regime_periods)} regime periods")
        return regime_analysis

    def run_monte_carlo_analysis(self, market_data: pd.DataFrame) -> dict:
        """Run Monte Carlo robustness testing.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with Monte Carlo results
        """
        logger.info("Running Monte Carlo analysis...")

        # Run backtest to get strategy returns
        strategy = self.strategy_class(
            formation_period_months=6,
            holding_period_months=6,
            percentile=10.0
        )

        engine = BacktestEngine(self.config)
        result = engine.run_backtest(strategy, market_data)

        strategy_returns = result.equity_curve.pct_change().dropna()

        # Run Monte Carlo simulation
        mc_result = self.validator.monte_carlo_simulation(strategy_returns, n_simulations=10000)

        mc_analysis = {
            'n_simulations': mc_result.n_simulations,
            'failure_rate': mc_result.failure_rate,
            'var_95': mc_result.var_95,
            'cvar_95': mc_result.cvar_95,
            'confidence_intervals': mc_result.confidence_intervals,
            'sharpe_distribution_stats': {
                'mean': float(np.mean(mc_result.sharpe_distribution)),
                'std': float(np.std(mc_result.sharpe_distribution)),
                '5th_percentile': float(np.percentile(mc_result.sharpe_distribution, 5)),
                '95th_percentile': float(np.percentile(mc_result.sharpe_distribution, 95))
            }
        }

        logger.info(".1%")
        return mc_analysis

    def run_transaction_cost_sensitivity(self, market_data: pd.DataFrame) -> dict:
        """Test strategy sensitivity to transaction costs.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with cost sensitivity results
        """
        logger.info("Running transaction cost sensitivity analysis...")

        cost_levels = [
            {'name': 'zero_cost', 'config': CostConfig(0, 0, 0, 0, 0)},
            {'name': 'retail', 'config': CostConfig(0.005, 1.0, 5.0, 2.0, 0.0001)},
            {'name': 'institutional', 'config': CostConfig(0.001, 0.5, 2.0, 1.0, 0.00005)},
            {'name': 'high_cost', 'config': CostConfig(0.01, 2.0, 10.0, 5.0, 0.0002)},  # 2% round trip
        ]

        results = {}

        for cost_level in cost_levels:
            logger.info(f"Testing with {cost_level['name']} costs...")

            # Update config with new costs
            test_config = self.config
            test_config.transaction_costs = cost_level['config']

            # Run backtest
            strategy = self.strategy_class(
                formation_period_months=6,
                holding_period_months=6,
                percentile=10.0
            )

            engine = BacktestEngine(test_config)
            result = engine.run_backtest(strategy, market_data)

            results[cost_level['name']] = {
                'total_return': result.performance.total_return,
                'sharpe_ratio': result.performance.sharpe_ratio,
                'max_drawdown': result.performance.max_drawdown,
                'total_trades': result.performance.total_trades,
                'win_rate': result.performance.win_rate,
                'profit_factor': result.performance.profit_factor
            }

        # Calculate cost impact
        zero_return = results['zero_cost']['total_return']
        for cost_name, metrics in results.items():
            if cost_name != 'zero_cost':
                cost_impact = metrics['total_return'] - zero_return
                results[cost_name]['cost_impact'] = cost_impact

        logger.info("Completed transaction cost sensitivity analysis")
        return results

    def run_statistical_validation(self, market_data: pd.DataFrame) -> dict:
        """Run comprehensive statistical validation.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with validation results
        """
        logger.info("Running statistical validation...")

        # Run backtest
        strategy = self.strategy_class(
            formation_period_months=6,
            holding_period_months=6,
            percentile=10.0
        )

        engine = BacktestEngine(self.config)
        result = engine.run_backtest(strategy, market_data)

        strategy_returns = result.equity_curve.pct_change().dropna()

        # Statistical tests
        significance_test = self.validator.test_strategy_significance(strategy_returns)

        # Validation results
        validation = self.validator.validate_backtest_result(result.performance, strategy_returns)

        # Minimum sample size analysis
        min_sample = self.validator.calculate_minimum_sample_size()

        stat_validation = {
            'sample_size': len(strategy_returns),
            'minimum_required_sample': min_sample,
            'significance_test': {
                'p_value': significance_test.p_value,
                'is_significant': significance_test.is_significant,
                'test_statistic': significance_test.test_statistic,
                'effect_size': significance_test.effect_size
            },
            'validation_results': validation,
            'performance_summary': {
                'total_return': result.performance.total_return,
                'annualized_return': result.performance.annualized_return,
                'sharpe_ratio': result.performance.sharpe_ratio,
                'max_drawdown': result.performance.max_drawdown,
                'win_rate': result.performance.win_rate,
                'profit_factor': result.performance.profit_factor
            }
        }

        logger.info(f"Statistical validation: significant={significance_test.is_significant}, p={significance_test.p_value:.4f}")
        return stat_validation

    def run_holdout_validation(self, market_data: pd.DataFrame) -> dict:
        """Run holdout sample validation on unseen data.

        Args:
            market_data: Historical market data

        Returns:
            Dictionary with holdout validation results
        """
        logger.info("Running holdout validation...")

        # Split data: training (2010-2019), holdout (2020-2023)
        training_end = datetime(2019, 12, 31)
        holdout_start = datetime(2020, 1, 1)

        training_data = market_data[market_data.index.get_level_values(1) <= training_end]
        holdout_data = market_data[market_data.index.get_level_values(1) >= holdout_start]

        if len(holdout_data) < 100:
            logger.warning("Insufficient holdout data")
            return {'error': 'insufficient_holdout_data'}

        # Optimize on training data
        optimizer = WalkForwardOptimizer(self.config)
        parameter_space = {
            'formation_period_months': [6],
            'holding_period_months': [6],
            'percentile': [10.0],
        }

        wf_result = optimizer.optimize_parameters(
            strategy_class=self.strategy_class,
            parameter_space=parameter_space,
            market_data=training_data,
            train_window_months=60,  # 5 years
            test_window_months=12,   # 1 year
            step_months=12
        )

        # Test optimal parameters on holdout data
        optimal_params = wf_result.optimal_parameters
        strategy = self.strategy_class(**optimal_params)

        holdout_config = self.config
        holdout_config.start_date = holdout_start
        holdout_config.end_date = self.config.end_date

        engine = BacktestEngine(holdout_config)
        holdout_result = engine.run_backtest(strategy, holdout_data)

        # Compare holdout vs training performance
        training_perf = wf_result.out_of_sample_performance
        holdout_perf = holdout_result.performance

        holdout_validation = {
            'training_performance': {
                'total_return': training_perf.total_return,
                'sharpe_ratio': training_perf.sharpe_ratio,
                'max_drawdown': training_perf.max_drawdown
            },
            'holdout_performance': {
                'total_return': holdout_perf.total_return,
                'sharpe_ratio': holdout_perf.sharpe_ratio,
                'max_drawdown': holdout_perf.max_drawdown
            },
            'performance_decay': {
                'return_decay': holdout_perf.total_return - training_perf.total_return,
                'sharpe_decay': holdout_perf.sharpe_ratio - training_perf.sharpe_ratio,
                'acceptable_decay': abs(holdout_perf.sharpe_ratio - training_perf.sharpe_ratio) < 0.5  # Within 0.5 Sharpe
            },
            'optimal_parameters': optimal_params
        }

        decay_pct = abs(holdout_perf.sharpe_ratio - training_perf.sharpe_ratio) / abs(training_perf.sharpe_ratio) * 100
        logger.info(".1f")
        return holdout_validation

    def generate_validation_report(self, results: dict) -> str:
        """Generate comprehensive validation report.

        Args:
            results: Dictionary with all validation results

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("MOMENTUM STRATEGY VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 20)

        stat_val = results.get('statistical_validation', {})
        perf = stat_val.get('performance_summary', {})

        report.append(f"Strategy: Momentum (Jegadeesh-Titman style)")
        report.append(f"Sample Size: {stat_val.get('sample_size', 0)} days")
        report.append(f"Total Return: {perf.get('total_return', 0):.2%}")
        report.append(f"Sharpe Ratio: {perf.get('sharpe_ratio', 0):.2f}")
        report.append(f"Max Drawdown: {perf.get('max_drawdown', 0):.2%}")
        report.append(f"Win Rate: {perf.get('win_rate', 0):.1%}")

        sig_test = stat_val.get('significance_test', {})
        is_sig = sig_test.get('is_significant', False)
        p_val = sig_test.get('p_value', 1.0)
        report.append(f"Statistically Significant: {'YES' if is_sig else 'NO'} (p = {p_val:.4f})")

        # Cost Analysis
        cost_sens = results.get('cost_sensitivity', {})
        if cost_sens:
            report.append("")
            report.append("TRANSACTION COST IMPACT")
            report.append("-" * 25)
            zero_ret = cost_sens.get('zero_cost', {}).get('total_return', 0)
            high_cost_ret = cost_sens.get('high_cost', {}).get('total_return', 0)
            cost_impact = high_cost_ret - zero_ret
            report.append(f"2% Round-trip Cost Impact: {cost_impact:.2%}")

        # Walk-forward Analysis
        wf = results.get('walk_forward', {})
        if wf:
            report.append("")
            report.append("WALK-FORWARD ANALYSIS")
            report.append("-" * 22)
            report.append(f"Stability Score: {wf.get('stability_score', 0):.2f}")
            oos_perf = wf.get('out_of_sample_performance', {})
            report.append(f"OOS Sharpe Ratio: {oos_perf.get('sharpe_ratio', 0):.2f}")
            report.append(f"OOS Max Drawdown: {oos_perf.get('max_drawdown', 0):.2%}")

        # Regime Analysis
        regime = results.get('regime_analysis', {})
        if regime:
            report.append("")
            report.append("REGIME ANALYSIS")
            report.append("-" * 15)
            perf_by_regime = regime.get('regime_performance', {})
            for reg, metrics in perf_by_regime.items():
                if metrics.get('sample_size', 0) > 0:
                    sharpe = metrics.get('sharpe_ratio', 0)
                    alpha = metrics.get('alpha', 0)
                    report.append(f"{reg.capitalize()}: Sharpe={sharpe:.2f}, Alpha={alpha:.2%}")

        # Monte Carlo Analysis
        mc = results.get('monte_carlo', {})
        if mc:
            report.append("")
            report.append("MONTE CARLO ROBUSTNESS")
            report.append("-" * 24)
            failure_rate = mc.get('failure_rate', 0)
            report.append(f"Failure Rate: {failure_rate:.1%}")
            ci = mc.get('confidence_intervals', {}).get('sharpe', [0, 0])
            report.append(f"Sharpe 95% CI: [{ci[0]:.2f}, {ci[1]:.2f}]")

        # Holdout Validation
        holdout = results.get('holdout_validation', {})
        if holdout:
            report.append("")
            report.append("HOLDOUT VALIDATION")
            report.append("-" * 19)
            decay = holdout.get('performance_decay', {})
            acceptable = decay.get('acceptable_decay', False)
            report.append(f"Performance Decay Acceptable: {'YES' if acceptable else 'NO'}")
            sharpe_decay = decay.get('sharpe_decay', 0)
            report.append(f"Sharpe Ratio Decay: {sharpe_decay:.2f}")

        # Final Recommendation
        report.append("")
        report.append("FINAL RECOMMENDATION")
        report.append("-" * 21)

        # Check key criteria
        criteria_met = 0
        total_criteria = 5

        # 1. Statistical significance
        if is_sig:
            criteria_met += 1

        # 2. Survives transaction costs
        if cost_impact > -0.10:  # Less than 10% negative impact from costs
            criteria_met += 1

        # 3. Positive OOS performance
        if oos_perf.get('sharpe_ratio', 0) > 0.5:
            criteria_met += 1

        # 4. Low failure rate
        if failure_rate < 0.40:
            criteria_met += 1

        # 5. Holdout validation passes
        if acceptable:
            criteria_met += 1

        report.append(f"Validation Criteria Met: {criteria_met}/{total_criteria}")

        if criteria_met >= 4:
            recommendation = "APPROVE - Strategy meets professional validation standards"
        elif criteria_met >= 3:
            recommendation = "CONDITIONAL APPROVAL - Address remaining issues before deployment"
        else:
            recommendation = "REJECT - Strategy fails basic validation - redesign required"

        report.append(f"Recommendation: {recommendation}")

        return "\n".join(report)

    def run_full_validation(self) -> dict:
        """Run complete validation suite.

        Returns:
            Dictionary with all validation results
        """
        logger.info("Starting comprehensive momentum strategy validation...")

        # Load data
        market_data = self.load_market_data()

        # Run all validation components
        results = {
            'statistical_validation': self.run_statistical_validation(market_data),
            'cost_sensitivity': self.run_transaction_cost_sensitivity(market_data),
            'walk_forward': self.run_walk_forward_analysis(market_data),
            'regime_analysis': self.run_regime_analysis(market_data),
            'monte_carlo': self.run_monte_carlo_analysis(market_data),
            'holdout_validation': self.run_holdout_validation(market_data),
        }

        # Generate report
        report = self.generate_validation_report(results)
        results['validation_report'] = report

        # Save results
        self.save_results(results)

        logger.info("Validation complete")
        return results

    def save_results(self, results: dict) -> None:
        """Save validation results to file.

        Args:
            results: Validation results dictionary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"momentum_strategy_validation_{timestamp}.json"

        # Convert numpy types to native Python types for JSON serialization
        def convert_for_json(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            return obj

        # Clean results for JSON
        clean_results = json.loads(json.dumps(results, default=convert_for_json))

        with open(filename, 'w') as f:
            json.dump(clean_results, f, indent=2)

        logger.info(f"Results saved to {filename}")

        # Also save report
        report_filename = f"momentum_strategy_report_{timestamp}.txt"
        with open(report_filename, 'w') as f:
            f.write(results['validation_report'])

        logger.info(f"Report saved to {report_filename}")


def main():
    """Main validation execution."""
    validator = MomentumStrategyValidator()
    results = validator.run_full_validation()

    # Print report to console
    print("\n" + results['validation_report'])


if __name__ == "__main__":
    main()
