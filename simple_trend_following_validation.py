#!/usr/bin/env python3
"""
Phase 2: Trend-Following Strategy Validation - Moving Average Crossover

Tests classic trend-following strategy with statistical rigor.
Based on Brock et al. (1992) research on technical trading rules.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from scipy import stats
import logging

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_market_data(symbol='SPY', start_date='2010-01-01', end_date='2023-12-31'):
    """Load clean market data for validation."""
    logger.info(f"Loading {symbol} data from {start_date} to {end_date}")

    df = yf.Ticker(symbol).history(start=start_date, end=end_date)

    if df.empty:
        raise ValueError(f"No data found for {symbol}")

    # Clean data
    df = df.dropna()
    df = df[df['Volume'] > 0]

    # Use adjusted close
    if 'Adj Close' in df.columns:
        price_data = df['Adj Close']
    else:
        price_data = df['Close']

    # Calculate returns
    price_data = price_data.pct_change().dropna()

    logger.info(f"Loaded {len(price_data)} daily returns for {symbol}")
    logger.info(f"Data range: {price_data.index[0]} to {price_data.index[-1]}")

    return price_data


def calculate_sma(prices, period):
    """Calculate simple moving average."""
    return prices.rolling(window=period).mean()


def detect_ma_crossover(fast_ma, slow_ma):
    """Detect moving average crossovers."""
    signals = pd.Series(0, index=fast_ma.index)

    # Bullish crossover: fast crosses above slow
    bullish_cross = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    signals[bullish_cross] = 1

    # Bearish crossover: fast crosses below slow
    bearish_cross = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    signals[bearish_cross] = -1

    return signals


def trend_following_strategy(returns, fast_period=50, slow_period=200):
    """Implement trend-following moving average crossover strategy.

    Args:
        returns: Daily return series
        fast_period: Fast moving average period
        slow_period: Slow moving average period

    Returns:
        Signal series (-1, 0, 1)
    """
    # Convert returns back to prices
    prices = (1 + returns).cumprod()
    prices = prices / prices.iloc[0]  # Normalize to start at 1

    # Calculate moving averages
    fast_ma = calculate_sma(prices, fast_period)
    slow_ma = calculate_sma(prices, slow_period)

    # Detect crossovers
    signals = detect_ma_crossover(fast_ma, slow_ma)

    # Forward fill signals (maintain position until next crossover)
    signals = signals.replace(0, np.nan).ffill().fillna(0)

    return signals


def backtest_strategy(returns, signals, transaction_cost=0.001):
    """Backtest the strategy with realistic costs."""
    # Calculate strategy returns
    strategy_returns = signals.shift(1) * returns

    # Apply transaction costs on signal changes
    signal_changes = signals.diff().abs() > 0
    strategy_returns.loc[signal_changes] -= transaction_cost

    return strategy_returns.dropna()


def calculate_performance_metrics(returns):
    """Calculate comprehensive performance metrics."""
    if len(returns) < 30:
        return {
            'total_return': 0.0,
            'annualized_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'p_value': 1.0,
            'is_significant': False
        }

    # Basic metrics
    total_return = (1 + returns).prod() - 1
    annualized_return = returns.mean() * 252
    volatility = returns.std() * np.sqrt(252)

    # Sharpe ratio
    risk_free_rate = 0.02  # Assume 2% risk-free rate
    sharpe = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = abs(drawdowns.min())

    # Win rate
    win_rate = (returns > 0).mean()

    # Statistical significance
    t_stat, p_value = stats.ttest_1samp(returns.values, 0)
    is_significant = p_value < 0.05

    return {
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'p_value': p_value,
        'is_significant': is_significant,
        't_statistic': t_stat
    }


def monte_carlo_simulation(strategy_returns, n_simulations=1000):
    """Run Monte Carlo simulation for robustness testing."""
    np.random.seed(42)

    # Bootstrap resampling
    simulated_sharpes = []
    simulated_returns = []
    simulated_drawdowns = []

    for _ in range(n_simulations):
        # Random sample with replacement
        sample = np.random.choice(strategy_returns.values, size=len(strategy_returns), replace=True)
        sample_returns = pd.Series(sample)

        # Calculate metrics for this sample
        metrics = calculate_performance_metrics(sample_returns)

        simulated_sharpes.append(metrics['sharpe_ratio'])
        simulated_returns.append(metrics['annualized_return'])
        simulated_drawdowns.append(metrics['max_drawdown'])

    # Calculate confidence intervals
    sharpe_ci = np.percentile(simulated_sharpes, [2.5, 97.5])
    return_ci = np.percentile(simulated_returns, [2.5, 97.5])
    drawdown_ci = np.percentile(simulated_drawdowns, [2.5, 97.5])

    return {
        'sharpe_ci': sharpe_ci,
        'return_ci': return_ci,
        'drawdown_ci': drawdown_ci,
        'sharpe_mean': np.mean(simulated_sharpes),
        'sharpe_std': np.std(simulated_sharpes),
        'failure_rate': np.mean(np.array(simulated_sharpes) < 0.5)
    }


def run_validation():
    """Run complete trend-following strategy validation."""
    print("=" * 70)
    print("PHASE 2: TREND-FOLLOWING STRATEGY VALIDATION")
    print("=" * 70)
    print("Classic Moving Average Crossover Strategy")
    print("• Fast MA (50-day) crosses above Slow MA (200-day) = BUY")
    print("• Fast MA (50-day) crosses below Slow MA (200-day) = SELL")
    print("• Hold position until next crossover")
    print("• Include transaction costs (0.1% round-trip)")
    print("• Monte Carlo robustness testing")
    print("=" * 70)

    try:
        # Load data
        print("\nLoading SPY data (2010-2023)...")
        market_returns = load_market_data('SPY', '2010-01-01', '2023-12-31')

        # Generate signals
        print("\nGenerating trend-following signals...")
        signals = trend_following_strategy(market_returns, fast_period=50, slow_period=200)
        signal_count = signals.abs().sum()
        long_signals = (signals == 1).sum()
        short_signals = (signals == -1).sum()
        neutral_signals = (signals == 0).sum()
        print(f"Generated {signal_count} crossover signals: {long_signals} long, {short_signals} short, {neutral_signals} neutral")

        # Backtest with costs
        print("\nBacktesting with transaction costs...")
        transaction_costs = [0.0, 0.001, 0.002]  # 0%, 0.1%, 0.2%
        results = {}

        for cost in transaction_costs:
            strategy_returns = backtest_strategy(market_returns, signals, cost)
            metrics = calculate_performance_metrics(strategy_returns)
            results[f'{cost*100:.1f}%'] = metrics

            print(f"\nCost Level: {cost*100:.1f}%")
            print(f"  Annualized Return: {metrics['annualized_return']:.1f}%")
            print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {metrics['max_drawdown']:.1%}")
            print(f"  P-value: {metrics['p_value']:.3f}")
            print(f"  Significant: {metrics['is_significant']}")

        # Monte Carlo analysis
        print("\nRunning Monte Carlo robustness testing (1,000 simulations)...")
        zero_cost_returns = backtest_strategy(market_returns, signals, 0.0)
        mc_results = monte_carlo_simulation(zero_cost_returns, 1000)

        print("Monte Carlo Results:")
        print(f"  Sharpe Ratio Mean: {mc_results['sharpe_mean']:.2f}")
        print(f"  Sharpe Ratio Std: {mc_results['sharpe_std']:.2f}")
        print(f"  Failure Rate: {mc_results['failure_rate']:.1f}")

        # Phase 2 success criteria
        zero_cost = results['0.0%']
        print("\n" + "=" * 70)
        print("PHASE 2 SUCCESS CRITERIA ASSESSMENT")
        print("=" * 70)

        criteria = [
            ("Sharpe Ratio > 0.8", zero_cost['sharpe_ratio'] > 0.8),
            ("Max Drawdown < 25%", zero_cost['max_drawdown'] < 0.25),
            ("Statistically Significant (p < 0.05)", zero_cost['is_significant']),
            ("Survives 0.1% costs (Sharpe > 0.5)", results['0.1%']['sharpe_ratio'] > 0.5),
            ("Monte Carlo Sharpe > 0.7", mc_results['sharpe_mean'] > 0.7)
        ]

        passed = 0
        for criterion, met in criteria:
            status = "✓" if met else "✗"
            print(f"{status} {criterion}")
            if met:
                passed += 1

        print(f"\nCriteria Met: {passed}/{len(criteria)}")

        # Recommendation
        print("\n" + "=" * 70)
        print("VALIDATION RECOMMENDATION")
        print("=" * 70)

        if passed >= 4:
            print("✅ STRATEGY PASSES VALIDATION")
            print("Ready for paper trading (Phase 2.7)")
            print("Next: Implement position sizing and risk management")
        elif passed >= 3:
            print("⚠️  STRATEGY MARGINAL - REQUIRES REFINEMENT")
            print("Consider parameter optimization or different MA periods")
        else:
            print("❌ STRATEGY REJECTED")
            print("This was our last attempt - all major strategy types failed")
            print("Recommendation: Focus on education before attempting live trading")

        return results, mc_results

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        return None, None


if __name__ == "__main__":
    run_validation()

if __name__ == "__main__":
    run_validation()
