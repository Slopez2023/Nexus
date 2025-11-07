#!/usr/bin/env python3
"""
Momentum Strategy Validation - Minimal Implementation
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from scipy import stats
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data(symbol='SPY', start='2010-01-01', end='2023-12-31'):
    """Load market data."""
    logger.info(f"Loading {symbol} data...")
    df = yf.Ticker(symbol).history(start=start, end=end)
    df['returns'] = df['Close'].pct_change()
    return df

def generate_signals(data, formation_days=126):
    """Generate momentum signals."""
    signals = []
    for i in range(formation_days, len(data) - 1):
        current_date = data.index[i]
        formation_data = data.iloc[i - formation_days:i + 1]
        cum_return = (formation_data['Close'].iloc[-1] / formation_data['Close'].iloc[0]) - 1

        signal = 1 if cum_return > 0 else -1
        confidence = min(abs(cum_return) * 5, 1.0)
        signals.append({'date': current_date, 'signal': signal, 'confidence': confidence})

    return pd.DataFrame(signals).set_index('date')

def calculate_returns(data, signals, transaction_cost=0.0):
    """Calculate strategy returns."""
    strategy_data = data.copy()
    strategy_data['signal'] = signals['signal'].reindex(strategy_data.index).fillna(0)
    strategy_data['signal'] = strategy_data['signal'].fillna(method='ffill').fillna(0)
    strategy_data['strategy_returns'] = strategy_data['signal'] * strategy_data['returns']

    # Apply costs on signal changes
    signal_changes = strategy_data['signal'].diff().fillna(0) != 0
    strategy_data.loc[signal_changes, 'strategy_returns'] -= transaction_cost

    return strategy_data

def calculate_metrics(returns):
    """Calculate performance metrics."""
    ret = returns['strategy_returns'].dropna()

    total_return = (1 + ret).prod() - 1
    annualized_return = ret.mean() * 252
    volatility = ret.std() * np.sqrt(252)
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0

    cumulative = (1 + ret).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_dd = abs(drawdowns.min())

    win_rate = (ret > 0).mean()

    t_stat, p_value = stats.ttest_1samp(ret.values, 0)

    return {
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'p_value': p_value,
        'is_significant': p_value < 0.05
    }

def main():
    """Run validation."""
    print("MOMENTUM STRATEGY VALIDATION")
    print("=" * 40)

    # Load data
    data = load_data()
    print(f"Loaded {len(data)} days of data")

    # Generate signals
    signals = generate_signals(data)
    print(f"Generated {len(signals)} signals")

    # Test different cost levels
    costs = [0.0, 0.005, 0.01, 0.02]
    results = {}

    for cost in costs:
        strategy_returns = calculate_returns(data, signals, cost)
        metrics = calculate_metrics(strategy_returns)
        results[f'{cost*100:.1f}%'] = metrics

        print(f"\nCost Level: {cost*100:.1f}%")
        print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"  Total Return: {metrics['total_return']:.2%}")
        print(f"  Max DD: {metrics['max_drawdown']:.1%}")
        print(f"  P-value: {metrics['p_value']:.3f}")
        print(f"  Significant: {metrics['is_significant']}")

    # Assessment
    zero_cost = results['0.0%']
    print("\n" + "=" * 40)
    print("ASSESSMENT")

    criteria_met = 0

    if zero_cost['sharpe_ratio'] > 0.8:
        print("✓ Sharpe > 0.8")
        criteria_met += 1
    else:
        print(f"✗ Sharpe {zero_cost['sharpe_ratio']:.2f} < 0.8")

    if zero_cost['max_drawdown'] < 0.25:
        print("✓ Max DD < 25%")
        criteria_met += 1
    else:
        print(f"✗ Max DD {zero_cost['max_drawdown']:.1%} > 25%")

    if zero_cost['is_significant']:
        print("✓ Statistically significant")
        criteria_met += 1
    else:
        print(f"✗ Not significant (p={zero_cost['p_value']:.3f})")

    # Cost survival
    survives_costs = any(results[f'{c*100:.1f}%']['sharpe_ratio'] > 0.5 for c in costs[1:])
    if survives_costs:
        print("✓ Survives transaction costs")
        criteria_met += 1
    else:
        print("✗ Does not survive costs")

    print(f"\nCriteria met: {criteria_met}/4")

    if criteria_met >= 3:
        print("RECOMMENDATION: Proceed with caution")
    else:
        print("RECOMMENDATION: Strategy needs redesign")

if __name__ == "__main__":
    main()
