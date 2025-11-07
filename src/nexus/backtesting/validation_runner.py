"""Validation runner for comprehensive strategy validation.

Orchestrates all validation methods: walk-forward analysis, Monte Carlo simulation,
multi-regime testing, and holdout validation into a unified workflow.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime
import logging

import pandas as pd

from .walk_forward import WalkForwardAnalyzer
from .validator import StatisticalValidator
from .regime_validator import RegimeValidator
from .holdout_validator import HoldoutValidator
from .comprehensive_report import ComprehensiveReportGenerator, ComprehensiveValidationReport

logger = logging.getLogger(__name__)


class ValidationRunner:
    """Comprehensive strategy validation orchestrator.

    Runs all validation methods systematically and generates
    integrated reports with actionable insights.
    """

    def __init__(
        self,
        enable_walk_forward: bool = True,
        enable_monte_carlo: bool = True,
        enable_regime_analysis: bool = True,
        enable_holdout: bool = True,
        monte_carlo_simulations: int = 10000,
        confidence_level: float = 0.95
    ):
        """Initialize validation runner.

        Args:
            enable_walk_forward: Whether to run walk-forward analysis
            enable_monte_carlo: Whether to run Monte Carlo simulation
            enable_regime_analysis: Whether to run regime analysis
            enable_holdout: Whether to run holdout validation
            monte_carlo_simulations: Number of Monte Carlo simulations
            confidence_level: Statistical confidence level
        """
        self.enable_walk_forward = enable_walk_forward
        self.enable_monte_carlo = enable_monte_carlo
        self.enable_regime_analysis = enable_regime_analysis
        self.enable_holdout = enable_holdout
        self.monte_carlo_simulations = monte_carlo_simulations
        self.confidence_level = confidence_level

        # Initialize validators
        self.walk_forward_analyzer = WalkForwardAnalyzer() if enable_walk_forward else None
        self.statistical_validator = StatisticalValidator(confidence_level=confidence_level)
        self.regime_validator = RegimeValidator() if enable_regime_analysis else None
        self.holdout_validator = HoldoutValidator(confidence_level=confidence_level) if enable_holdout else None
        self.report_generator = ComprehensiveReportGenerator()

    def run_comprehensive_validation(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        parameter_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        benchmark_returns: Optional[pd.Series] = None,
        strategy_name: str = "Trading Strategy"
    ) -> ComprehensiveValidationReport:
        """Run comprehensive validation suite.

        Args:
            strategy_func: Strategy function that generates signals
            price_data: Historical price data with datetime index
            parameter_ranges: Parameter ranges for optimization (optional)
            strategy_params: Fixed strategy parameters (optional)
            benchmark_returns: Benchmark returns for comparison
            strategy_name: Name of the strategy

        Returns:
            ComprehensiveValidationReport: Complete validation results
        """
        logger.info(f"Starting comprehensive validation for {strategy_name}")

        start_time = datetime.now()

        # Initialize results
        walk_forward_result = None
        monte_carlo_result = None
        regime_result = None
        holdout_result = None

        # Run walk-forward analysis
        if self.enable_walk_forward:
            logger.info("Running walk-forward analysis...")
            try:
                walk_forward_result = self.walk_forward_analyzer.analyze(
                    strategy_func=strategy_func,
                    price_data=price_data,
                    parameter_ranges=parameter_ranges,
                    initial_capital=100000.0,
                    start_date=price_data.index[0],
                    end_date=price_data.index[-1]
                )
                logger.info("Walk-forward analysis completed")
            except Exception as e:
                logger.error(f"Walk-forward analysis failed: {e}")
                walk_forward_result = None

        # Generate strategy returns for other validations
        logger.info("Generating strategy returns for additional validations...")
        strategy_returns = self._generate_strategy_returns(
            strategy_func, price_data, strategy_params or {}
        )

        # Run Monte Carlo simulation
        if self.enable_monte_carlo and strategy_returns is not None:
            logger.info(f"Running Monte Carlo simulation ({self.monte_carlo_simulations} simulations)...")
            try:
                monte_carlo_result = self.statistical_validator.monte_carlo_simulation(
                    strategy_returns=strategy_returns,
                    n_simulations=self.monte_carlo_simulations
                )
                logger.info("Monte Carlo simulation completed")
            except Exception as e:
                logger.error(f"Monte Carlo simulation failed: {e}")
                monte_carlo_result = None

        # Run multi-regime analysis
        if self.enable_regime_analysis and strategy_returns is not None:
            logger.info("Running multi-regime analysis...")
            try:
                regime_result = self.regime_validator.validate_strategy_regime_performance(
                    strategy_returns=strategy_returns,
                    price_data=price_data,
                    benchmark_returns=benchmark_returns
                )
                logger.info("Multi-regime analysis completed")
            except Exception as e:
                logger.error(f"Multi-regime analysis failed: {e}")
                regime_result = None

        # Run holdout validation
        if self.enable_holdout:
            logger.info("Running holdout validation...")
            try:
                holdout_result = self.holdout_validator.validate_strategy_holdout(
                    strategy_func=strategy_func,
                    price_data=price_data,
                    parameter_ranges=parameter_ranges,
                    strategy_params=strategy_params
                )
                logger.info("Holdout validation completed")
            except Exception as e:
                logger.error(f"Holdout validation failed: {e}")
                holdout_result = None

        # Generate comprehensive report
        logger.info("Generating comprehensive validation report...")
        try:
            report = self.report_generator.generate_comprehensive_report(
                walk_forward=walk_forward_result,
                monte_carlo=monte_carlo_result,
                regime_analysis=regime_result,
                holdout=holdout_result,
                strategy_name=strategy_name
            )
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            # Create minimal report
            report = self._create_minimal_report(strategy_name)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"Comprehensive validation completed in {duration:.1f} seconds")
        logger.info(f"Final recommendation: {report.summary.recommendation}")

        return report

    def _generate_strategy_returns(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        params: Dict[str, Any]
    ) -> Optional[pd.Series]:
        """Generate strategy returns for validation.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            params: Strategy parameters

        Returns:
            Strategy returns series or None if generation fails
        """
        try:
            # Generate signals
            signals = strategy_func(price_data, **params)

            # Calculate returns (simple long/short strategy)
            returns = signals.shift(1) * price_data.pct_change()
            returns = returns.dropna()

            return returns

        except Exception as e:
            logger.warning(f"Strategy returns generation failed: {e}")
            return None

    def _create_minimal_report(self, strategy_name: str) -> ComprehensiveValidationReport:
        """Create minimal report when validation fails."""
        from .comprehensive_report import ValidationSummary
        from .models import PerformanceMetrics

        empty_performance = PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, volatility=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
            calmar_ratio=0.0, win_rate=0.0, profit_factor=0.0,
            total_trades=0, avg_trade_pnl=0.0, best_trade=0.0, worst_trade=0.0
        )

        summary = ValidationSummary(
            overall_confidence="Low",
            recommendation="Reject",
            key_strengths=[],
            key_weaknesses=["Validation failed - unable to complete analysis"],
            risk_assessment="Unable to assess - validation failed",
            generalization_score=0.0
        )

        return ComprehensiveValidationReport(
            summary=summary,
            walk_forward_analysis=None,
            monte_carlo_analysis=None,
            regime_analysis=None,
            holdout_analysis=None,
            overall_performance_score=0.0,
            robustness_score=0.0,
            risk_adjusted_score=0.0,
            suggested_improvements=["Debug and fix validation pipeline"],
            risk_mitigation_strategies=["Do not deploy strategy"],
            deployment_readiness="Not ready - validation failed",
            generated_at=datetime.now(),
            validation_methods_used=[]
        )

    def run_quick_validation(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        strategy_params: Optional[Dict[str, Any]] = None,
        strategy_name: str = "Trading Strategy"
    ) -> ComprehensiveValidationReport:
        """Run quick validation with reduced scope.

        Suitable for rapid feedback during development.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            strategy_params: Strategy parameters
            strategy_name: Strategy name

        Returns:
            ComprehensiveValidationReport: Quick validation results
        """
        logger.info(f"Running quick validation for {strategy_name}")

        # Generate strategy returns
        strategy_returns = self._generate_strategy_returns(
            strategy_func, price_data, strategy_params or {}
        )

        if strategy_returns is None:
            return self._create_minimal_report(strategy_name)

        # Run only Monte Carlo and basic regime analysis
        monte_carlo_result = None
        regime_result = None

        # Monte Carlo (reduced simulations for speed)
        if self.enable_monte_carlo:
            try:
                monte_carlo_result = self.statistical_validator.monte_carlo_simulation(
                    strategy_returns=strategy_returns,
                    n_simulations=min(1000, self.monte_carlo_simulations)
                )
            except Exception as e:
                logger.warning(f"Monte Carlo failed in quick validation: {e}")

        # Basic regime analysis
        if self.enable_regime_analysis:
            try:
                regime_result = self.regime_validator.validate_strategy_regime_performance(
                    strategy_returns=strategy_returns,
                    price_data=price_data
                )
            except Exception as e:
                logger.warning(f"Regime analysis failed in quick validation: {e}")

        # Generate report
        report = self.report_generator.generate_comprehensive_report(
            walk_forward=None,
            monte_carlo=monte_carlo_result,
            regime_analysis=regime_result,
            holdout=None,
            strategy_name=strategy_name
        )

        return report

    def _generate_strategy_returns(
        self,
        strategy_func: Callable,
        price_data: pd.Series,
        params: Dict[str, Any]
    ) -> Optional[pd.Series]:
        """Generate strategy returns for validation.

        Args:
            strategy_func: Strategy function
            price_data: Price data
            params: Strategy parameters

        Returns:
            Strategy returns series or None if generation fails
        """
        try:
            # Generate signals
            signals = strategy_func(price_data, **params)

            # Calculate returns (simple long/short strategy)
            returns = signals.shift(1) * price_data.pct_change()
            returns = returns.dropna()

            return returns

        except Exception as e:
            logger.warning(f"Strategy returns generation failed: {e}")
            return None

    def validate_momentum_strategy(
        self,
        price_data: pd.Series,
        formation_days: int = 126,
        strategy_name: str = "Momentum Strategy"
    ) -> ComprehensiveValidationReport:
        """Validate the momentum strategy specifically.

        Args:
            price_data: Price data
            formation_days: Momentum formation period
            strategy_name: Strategy name

        Returns:
            ComprehensiveValidationReport: Validation results
        """
        def momentum_strategy(data: pd.Series, formation_days: int = 126) -> pd.Series:
            """Simple momentum strategy."""
            signals = pd.Series(index=data.index, dtype=float)

            for i in range(formation_days, len(data) - 1):
                current_date = data.index[i]
                formation_data = data.iloc[i - formation_days:i + 1]
                cum_return = (formation_data.iloc[-1] / formation_data.iloc[0]) - 1

                signal = 1 if cum_return > 0 else -1
                signals.loc[current_date] = signal

            signals = signals.fillna(0)  # Neutral before sufficient data
            return signals

        # Parameter ranges for optimization
        parameter_ranges = {
            'formation_days': (50, 200)  # Test different formation periods
        }

        # Fixed parameters for this run
        strategy_params = {'formation_days': formation_days}

        return self.run_comprehensive_validation(
            strategy_func=momentum_strategy,
            price_data=price_data,
            parameter_ranges=parameter_ranges,
            strategy_params=strategy_params,
            strategy_name=strategy_name
        )

    def print_validation_status(self, report: ComprehensiveValidationReport) -> None:
        """Print validation status summary."""
        print(f"\n{'='*50}")
        print("VALIDATION STATUS SUMMARY")
        print(f"{'='*50}")

        print(f"Strategy: {report.deployment_readiness}")
        print(f"Confidence: {report.summary.overall_confidence}")
        print(f"Recommendation: {report.summary.recommendation}")

        print(f"\nPerformance Scores:")
        print(f"  Overall Performance: {report.overall_performance_score:.2f}")
        print(f"  Robustness: {report.robustness_score:.2f}")
        print(f"  Risk-Adjusted: {report.risk_adjusted_score:.2f}")

        print(f"\nMethods Used: {', '.join(report.validation_methods_used)}")

        if report.summary.key_strengths:
            print(f"\nKey Strengths:")
            for strength in report.summary.key_strengths[:3]:  # Top 3
                print(f"  ✓ {strength}")

        if report.summary.key_weaknesses:
            print(f"\nKey Weaknesses:")
            for weakness in report.summary.key_weaknesses[:3]:  # Top 3
                print(f"  ✗ {weakness}")

        print(f"\nNext Steps: {report.suggested_improvements[0] if report.suggested_improvements else 'None'}")
        print(f"{'='*50}")
