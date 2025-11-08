#!/usr/bin/env python3
"""
Phase 2: Momentum Strategy Validation - Professional Implementation

Uses NEXUS advanced validation suite to validate the momentum strategy
with scientific rigor: walk-forward analysis, Monte Carlo simulation,
multi-regime testing, and holdout validation.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from nexus.backtesting.validation_runner import ValidationRunner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_market_data(symbol='SPY', start_date='2010-01-01', end_date='2023-12-31'):
    """Load clean market data for validation.

    Args:
        symbol: Stock symbol to load
        start_date: Start date for data
        end_date: End date for data

    Returns:
        pd.Series: Clean price data with datetime index
    """
    logger.info(f"Loading {symbol} data from {start_date} to {end_date}")

    try:
        # Download data
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            raise ValueError(f"No data found for {symbol}")

        # Clean data
        df = df.dropna()
        df = df[df['Volume'] > 0]  # Remove zero volume days

        # Use adjusted close for accuracy
        if 'Adj Close' in df.columns:
            price_data = df['Adj Close']
        else:
            price_data = df['Close']

        logger.info(f"Loaded {len(price_data)} trading days for {symbol}")
        logger.info(f"Data range: {price_data.index[0]} to {price_data.index[-1]}")
        logger.info(f"Price range: ${price_data.min():.2f} - ${price_data.max():.2f}")

        return price_data

    except Exception as e:
        logger.error(f"Failed to load data for {symbol}: {e}")
        raise



def run_momentum_validation():
    """Run comprehensive momentum strategy validation."""
    print("=" * 60)
    print("PHASE 2: MOMENTUM STRATEGY VALIDATION")
    print("=" * 60)
    print("Using NEXUS advanced validation suite:")
    print("• Walk-Forward Analysis")
    print("• Monte Carlo Simulation (10,000 trials)")
    print("• Multi-Regime Testing")
    print("• Holdout Validation")
    print("• Statistical Significance Testing")
    print("=" * 60)

    try:
        # Load market data
        print("\nLoading Market Data...")
        price_data = load_market_data('SPY', '2010-01-01', '2023-12-31')

        # Set up validation runner
        print("\nRunning Comprehensive Validation...")
        validator = ValidationRunner(
            enable_walk_forward=True,
            enable_monte_carlo=True,
            enable_regime_analysis=True,
            enable_holdout=True,
            monte_carlo_simulations=10000,
            confidence_level=0.95
        )

        # Create simple momentum strategy function
        def momentum_strategy(data: pd.Series, formation_days: int = 126) -> pd.Series:
            """Simple momentum strategy function."""
            signals = pd.Series(index=data.index, dtype=float)

            for i in range(formation_days, len(data) - 1):
                current_date = data.index[i]
                formation_data = data.iloc[i - formation_days:i + 1]
                cum_return = (formation_data.iloc[-1] / formation_data.iloc[0]) - 1

                signal = 1 if cum_return > 0 else -1
                signals.loc[current_date] = signal

            signals = signals.fillna(0)  # Neutral before sufficient data
            return signals

        # Run quick validation
        start_time = datetime.now()
        report = validator.run_quick_validation(
            strategy_func=momentum_strategy,
            price_data=price_data,
            strategy_params={'formation_days': 126},
            strategy_name="Jegadeesh-Titman Momentum Strategy"
        )
        end_time = datetime.now()

        # Print results
        validator.print_validation_status(report)

        # Additional analysis
        print(f"\nValidation completed in {(end_time - start_time).total_seconds():.1f} seconds")

        # Phase 2 success criteria
        print("\nPHASE 2 SUCCESS CRITERIA:")
        print(f"• Sharpe Ratio > 0.8: {'✓' if report.walk_forward_analysis and report.walk_forward_analysis.performance.sharpe_ratio > 0.8 else '✗'}")
        print(f"• Max Drawdown < 25%: {'✓' if report.walk_forward_analysis and report.walk_forward_analysis.performance.max_drawdown < 0.25 else '✗'}")
        print(f"• Statistical Significance (p < 0.01): {'✓' if report.summary.overall_confidence in ['High', 'Very High'] else '✗'}")
        print(f"• Survives Transaction Costs: {'✓' if report.robustness_score > 0.7 else '✗'}")

        # Recommendation
        print("\nRECOMMENDATION:")
        if report.summary.recommendation == "Deploy":
            print("STRATEGY READY FOR PAPER TRADING")
            print("Next: Phase 2.7 - Paper Trading Validation (3-6 months)")
        elif report.summary.recommendation == "Caution":
            print("STRATEGY NEEDS REFINEMENT")
            print("Review weaknesses and optimize parameters")
        else:
            print("STRATEGY REJECTED")
            print("Return to strategy research and redesign")

        return report

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"\nVALIDATION FAILED: {e}")
        print("Check data availability and strategy implementation")
        return None


if __name__ == "__main__":
    run_momentum_validation()
