#!/usr/bin/env python3
"""
Advanced Validation Demo for Momentum Strategy

Demonstrates the comprehensive validation suite with:
- Walk-forward analysis (rolling time windows, out-of-sample testing)
- Monte Carlo simulation (10,000 bootstrap tests, confidence intervals)
- Multi-regime testing (bull/bear/sideways market performance)
- Holdout validation (unseen 2020-2023 data testing)
- Comprehensive validation report (all results synthesis)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
import yfinance as yf
from datetime import datetime
import logging

from nexus.backtesting import ValidationRunner

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_market_data(symbol='SPY', start_date='2010-01-01', end_date='2023-12-31'):
    """Load market data for validation."""
    logger.info(f"Loading {symbol} data from {start_date} to {end_date}")

    try:
        data = yf.Ticker(symbol).history(start=start_date, end=end_date)
        if data.empty:
            raise ValueError(f"No data available for {symbol}")

        # Use adjusted close for more accurate returns
        price_data = data['Adj Close'] if 'Adj Close' in data.columns else data['Close']
        price_data = price_data.dropna()

        logger.info(f"Loaded {len(price_data)} days of data")
        return price_data

    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        raise


def momentum_strategy(price_data: pd.Series, formation_days: int = 126) -> pd.Series:
    """Simple momentum strategy implementation.

    Args:
        price_data: Price series with datetime index
        formation_days: Number of days to look back for momentum calculation

    Returns:
        Series of signals (-1, 0, 1) with datetime index
    """
    signals = pd.Series(index=price_data.index, dtype=float)

    for i in range(formation_days, len(price_data)):
        current_date = price_data.index[i]

        # Calculate momentum over formation period
        formation_start = price_data.index[i - formation_days]
        formation_end = price_data.index[i]

        start_price = price_data.loc[formation_start]
        end_price = price_data.loc[formation_end]

        # Momentum as cumulative return
        momentum = (end_price / start_price) - 1

        # Generate signal based on momentum
        if momentum > 0:
            signal = 1.0  # Long
        else:
            signal = -1.0  # Short

        signals.loc[current_date] = signal

    # Fill initial period with neutral signal
    signals = signals.fillna(0.0)

    return signals


def main():
    """Run comprehensive validation demo."""
    print("🔬 ADVANCED VALIDATION DEMO - MOMENTUM STRATEGY")
    print("=" * 60)

    try:
        # Load market data
        price_data = load_market_data('SPY', '2010-01-01', '2023-12-31')

        # Define parameter ranges for optimization
        parameter_ranges = {
            'formation_days': (50, 200)  # Test different formation periods
        }

        # Create validation runner with all methods enabled
        validator = ValidationRunner(
            enable_walk_forward=True,
            enable_monte_carlo=True,
            enable_regime_analysis=True,
            enable_holdout=True,
            monte_carlo_simulations=10000,  # Full Monte Carlo
            confidence_level=0.95
        )

        print("\n🚀 Starting comprehensive validation...")
        print("This may take several minutes due to 10,000 Monte Carlo simulations...")

        # Run comprehensive validation
        report = validator.run_comprehensive_validation(
            strategy_func=momentum_strategy,
            price_data=price_data,
            parameter_ranges=parameter_ranges,
            strategy_params={'formation_days': 126},  # Default parameters
            strategy_name="SPY Momentum Strategy"
        )

        # Print executive summary
        print("\n📊 EXECUTIVE SUMMARY")
        print("=" * 40)

        validator.report_generator.print_executive_summary(report)

        # Print detailed results
        print("\n📈 DETAILED RESULTS")
        print("=" * 40)

        if report.walk_forward_analysis:
            wf = report.walk_forward_analysis
            print(f"Walk-Forward Analysis:")
            print(f"  Windows: {len(wf.window_results)}")
            print(".2f")
            print(".3f")
            print()

        if report.monte_carlo_analysis:
            mc = report.monte_carlo_analysis
            print(f"Monte Carlo Simulation:")
            print(f"  Simulations: {mc.n_simulations:,}")
            print(".1%")
            print(".3f")
            print(".3f")
            print()

        if report.regime_analysis:
            regime = report.regime_analysis
            print(f"Multi-Regime Analysis:")
            print(f"  Best Regime: {regime.best_regime}")
            print(f"  Worst Regime: {regime.worst_regime}")
            print(".2f")
            print(".2f")
            print()

        if report.holdout_analysis:
            holdout = report.holdout_analysis
            print(f"Holdout Validation:")
            print(f"  Periods: {len(holdout.holdout_periods)}")
            print(".2f")
            print(".3f")
            print(f"  Overfitting Detected: {holdout.overfitting_detected}")
            print()

        print("✅ Validation completed successfully!")
        print(f"📄 Full report saved with timestamp: {report.generated_at.strftime('%Y%m%d_%H%M%S')}")

        # Export report to dictionary for potential JSON serialization
        report_dict = validator.report_generator.export_report_to_dict(report)

        return report

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"\n❌ Validation failed: {e}")
        raise


def quick_validation_demo():
    """Run quick validation for faster feedback."""
    print("⚡ QUICK VALIDATION DEMO")
    print("=" * 40)

    try:
        # Load data
        price_data = load_market_data('SPY', '2018-01-01', '2023-12-31')  # Shorter period

        # Create validator with reduced scope
        validator = ValidationRunner(
            enable_walk_forward=False,  # Skip for speed
            enable_monte_carlo=True,
            enable_regime_analysis=True,
            enable_holdout=False,  # Skip for speed
            monte_carlo_simulations=1000  # Reduced simulations
        )

        # Run quick validation
        report = validator.run_quick_validation(
            strategy_func=momentum_strategy,
            price_data=price_data,
            strategy_params={'formation_days': 126},
            strategy_name="SPY Momentum (Quick Test)"
        )

        # Print summary
        validator.print_validation_status(report)

        return report

    except Exception as e:
        logger.error(f"Quick validation failed: {e}")
        print(f"❌ Quick validation failed: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Advanced Validation Demo")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick validation instead of comprehensive")
    parser.add_argument("--symbol", default="SPY",
                       help="Stock symbol to test (default: SPY)")

    args = parser.parse_args()

    if args.quick:
        quick_validation_demo()
    else:
        main()
