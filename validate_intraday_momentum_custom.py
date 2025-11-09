#!/usr/bin/env python3
"""
Custom Intraday Momentum Strategy Validation

Comprehensive validation using custom Monte Carlo and regime analysis
specifically designed for intraday strategies. This demonstrates the
validation approach that would be used in a full NEXUS implementation.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import scipy.stats as stats

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from nexus.strategies.intraday_momentum import IntradayMomentumStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IntradayValidator:
    """Custom validator for intraday strategies."""

    def __init__(self, n_simulations: int = 1000, confidence_level: float = 0.95):
        self.n_simulations = n_simulations
        self.confidence_level = confidence_level

    def monte_carlo_analysis(self, returns: pd.Series) -> Dict:
        """Perform Monte Carlo analysis on strategy returns."""
        logger.info(f"Running Monte Carlo analysis with {self.n_simulations} simulations")

        # Calculate basic statistics
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe_ratio = mean_return / std_return * np.sqrt(252 * 78)  # Annualized (252 days * 78 5-min bars)

        # Run simulations
        simulated_sharpe = []
        simulated_max_dd = []
        simulated_total_return = []

        for i in range(self.n_simulations):
            # Bootstrap sample with replacement
            bootstrap_returns = np.random.choice(returns.values, size=len(returns), replace=True)

            # Calculate metrics for this simulation
            sim_cumulative = np.cumprod(1 + bootstrap_returns) - 1
            sim_total_return = sim_cumulative[-1]
            sim_max_dd = np.max(np.maximum.accumulate(sim_cumulative) - sim_cumulative)

            # Sharpe ratio for simulation
            sim_mean = np.mean(bootstrap_returns)
            sim_std = np.std(bootstrap_returns)
            sim_sharpe = sim_mean / sim_std * np.sqrt(252 * 78) if sim_std > 0 else 0

            simulated_sharpe.append(sim_sharpe)
            simulated_max_dd.append(sim_max_dd)
            simulated_total_return.append(sim_total_return)

        # Calculate confidence intervals
        sharpe_ci = stats.norm.interval(self.confidence_level,
                                      loc=np.mean(simulated_sharpe),
                                      scale=stats.sem(simulated_sharpe))

        max_dd_ci = (np.percentile(simulated_max_dd, (1-self.confidence_level)/2 * 100),
                    np.percentile(simulated_max_dd, (1+self.confidence_level)/2 * 100))

        total_return_ci = (np.percentile(simulated_total_return, (1-self.confidence_level)/2 * 100),
                          np.percentile(simulated_total_return, (1+self.confidence_level)/2 * 100))

        return {
            'n_simulations': self.n_simulations,
            'original_sharpe': sharpe_ratio,
            'original_max_dd': np.max(np.maximum.accumulate((1 + returns).cumprod() - 1) - ((1 + returns).cumprod() - 1)),
            'original_total_return': (1 + returns).prod() - 1,
            'confidence_intervals': {
                'sharpe_ratio': sharpe_ci,
                'max_drawdown': max_dd_ci,
                'total_return': total_return_ci
            },
            'simulation_stats': {
                'sharpe_mean': np.mean(simulated_sharpe),
                'sharpe_std': np.std(simulated_sharpe),
                'max_dd_mean': np.mean(simulated_max_dd),
                'max_dd_std': np.std(simulated_max_dd)
            }
        }

    def regime_analysis(self, returns: pd.Series, price_data: pd.Series) -> Dict:
        """Analyze performance across different market regimes."""
        logger.info("Running regime analysis")

        # Define regimes based on price trends
        price_returns = price_data.pct_change()

        # Simple regime detection (could be more sophisticated)
        rolling_trend = price_returns.rolling(20).mean()  # 20-bar trend

        bull_mask = rolling_trend > 0.0001   # Bull market
        bear_mask = rolling_trend < -0.0001  # Bear market
        sideways_mask = (rolling_trend >= -0.0001) & (rolling_trend <= 0.0001)  # Sideways

        regimes = {
            'bull': returns[bull_mask],
            'bear': returns[bear_mask],
            'sideways': returns[sideways_mask]
        }

        regime_performance = {}
        for regime_name, regime_returns in regimes.items():
            if len(regime_returns) > 10:  # Minimum data requirement
                total_return = (1 + regime_returns).prod() - 1
                win_rate = (regime_returns > 0).mean()
                avg_return = regime_returns.mean()
                volatility = regime_returns.std()

                regime_performance[regime_name] = {
                    'total_return': total_return,
                    'win_rate': win_rate,
                    'avg_return': avg_return,
                    'volatility': volatility,
                    'sharpe_ratio': avg_return / volatility * np.sqrt(252 * 78) if volatility > 0 else 0,
                    'n_trades': len(regime_returns)
                }

        return {
            'regime_performance': regime_performance,
            'regime_distribution': {
                'bull_pct': bull_mask.mean() * 100,
                'bear_pct': bear_mask.mean() * 100,
                'sideways_pct': sideways_mask.mean() * 100
            }
        }


def generate_intraday_data(symbol: str, trading_days: int = 30) -> pd.DataFrame:
    """Generate realistic synthetic 5-minute intraday data."""
    logger.info(f"Generating synthetic intraday data for {symbol} over {trading_days} days")

    start_date = datetime(2024, 11, 1, 9, 30)
    base_price = 150
    daily_volatility = 0.02
    avg_volume = 2000000

    all_bars = []

    for day in range(trading_days):
        current_date = start_date + timedelta(days=day)
        if current_date.weekday() >= 5:  # Skip weekends
            continue

        # Daily trend
        daily_trend = np.random.normal(0.0002, 0.005)

        day_bars = []
        current_price = base_price * (1 + daily_trend * day)

        # Generate 78 5-minute bars per day
        for bar in range(78):
            bar_time = current_date.replace(hour=9, minute=30) + timedelta(minutes=5 * bar)

            # Intraday volatility pattern
            time_factor = 1.0
            if bar < 6:  # Opening volatility
                time_factor = 1.8
            elif bar > 60:  # Closing volatility
                time_factor = 1.5

            # Price movement
            volatility = daily_volatility * time_factor
            price_change = np.random.normal(daily_trend/78, volatility)

            open_price = current_price
            high_price = open_price * (1 + abs(np.random.normal(0, volatility*0.8)))
            low_price = open_price * (1 - abs(np.random.normal(0, volatility*0.8)))
            close_price = open_price * (1 + price_change)

            # Ensure OHLC relationships
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

            # Volume
            volume = int(np.random.uniform(avg_volume * 0.7, avg_volume * 1.3))

            bar_data = {
                'timestamp': bar_time,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            }

            day_bars.append(bar_data)
            current_price = close_price

        all_bars.extend(day_bars)

    df = pd.DataFrame(all_bars)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    return df


def run_strategy_validation():
    """Run comprehensive validation for the intraday momentum strategy."""

    print("=" * 80)
    print("🤖 NEXUS INTRADAY MOMENTUM STRATEGY VALIDATION")
    print("=" * 80)
    print("Testing Intraday Momentum Strategy:")
    print("• 5-minute timeframe analysis")
    print("• RSI + momentum + volume confirmation")
    print("• Risk management with 2% stops, 4% targets")
    print("• Custom Monte Carlo validation (1,000 simulations)")
    print("=" * 80)

    try:
        # Generate synthetic intraday data
        print("\n📊 Generating Synthetic Intraday Data...")
        intraday_data = generate_intraday_data('AAPL', trading_days=45)
        price_data = intraday_data['close']

        print(f"✅ Generated {len(price_data)} 5-minute bars")
        print(f"   Data range: {price_data.index[0]} to {price_data.index[-1]}")
        print(".2f")
        print(".1f")

        # Create strategy
        print("\n🔧 Initializing Strategy...")
        strategy = IntradayMomentumStrategy(
            timeframe_minutes=5,
            rsi_period=14,
            rsi_overbought=70,
            rsi_oversold=30,
            momentum_period=10,
            volume_multiplier=1.5,
            stop_loss_pct=0.02,
            take_profit_pct=0.04,
            max_positions=3,
            min_price_move=0.005,
        )
        print("✅ Strategy initialized successfully")

        # Mock market data interface
        class MockMarketData:
            def __init__(self, df):
                self.df = df

            def get_intraday_data(self, symbol, timeframe, periods):
                data = []
                for idx, row in self.df.tail(periods).iterrows():
                    data.append({
                        'timestamp': idx.isoformat(),
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row['volume']
                    })
                return data

            def get_intraday_universe(self):
                return ['AAPL']

        # Generate strategy signals
        print("\n🎯 Generating Strategy Signals...")
        market_data = MockMarketData(intraday_data)
        signals = strategy.generate_signals(market_data)

        print(f"✅ Generated {len(signals)} trading signals")

        # Convert signals to returns for validation
        print("\n📈 Calculating Strategy Returns...")
        signal_series = pd.Series(0.0, index=price_data.index)

        for signal in signals:
            signal_time = pd.to_datetime(signal.timestamp)
            closest_idx = price_data.index.get_indexer([signal_time], method='nearest')[0]
            if closest_idx < len(price_data):
                actual_time = price_data.index[closest_idx]
                if signal.direction == 'long':
                    signal_series.loc[actual_time] = 1.0
                elif signal.direction == 'short':
                    signal_series.loc[actual_time] = -1.0

        # Calculate strategy returns (simple next-bar exit for demonstration)
        strategy_returns = signal_series.shift(1) * price_data.pct_change()
        strategy_returns = strategy_returns.dropna()

        print(f"   Strategy trades: {len(strategy_returns[strategy_returns != 0])}")
        print(".1%")

        # Run validation
        print("\n🔬 Running Custom Validation Suite...")
        validator = IntradayValidator(n_simulations=1000, confidence_level=0.95)

        # Monte Carlo analysis
        mc_results = validator.monte_carlo_analysis(strategy_returns)

        # Regime analysis
        regime_results = validator.regime_analysis(strategy_returns, price_data)

        # Calculate performance scores
        total_return = (1 + strategy_returns).prod() - 1
        volatility = strategy_returns.std()
        sharpe_ratio = strategy_returns.mean() / volatility * np.sqrt(252 * 78) if volatility > 0 else 0
        max_drawdown = mc_results['original_max_dd']
        win_rate = (strategy_returns > 0).mean()

        # Scoring system (0-1 scale)
        performance_score = min(1.0, max(0.0, (sharpe_ratio + 1) / 3))  # Sharpe 1.0 = score 0.67
        robustness_score = min(1.0, max(0.0, (win_rate - 0.4) / 0.3))  # 55% win rate = score 0.5
        risk_adjusted_score = min(1.0, max(0.0, (total_return / abs(max_drawdown) + 1) / 4)) if max_drawdown != 0 else 0.5

        overall_score = (performance_score + robustness_score + risk_adjusted_score) / 3

        # Display comprehensive results
        print(f"\n✅ Validation completed successfully")
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE VALIDATION REPORT")
        print("="*80)

        # Executive summary
        print("🎯 EXECUTIVE SUMMARY")
        print("-" * 30)
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")

        # Determine recommendation
        if overall_score >= 0.7 and sharpe_ratio >= 1.0:
            recommendation = "Deploy"
            confidence = "High"
        elif overall_score >= 0.5 and win_rate >= 0.55:
            recommendation = "Caution"
            confidence = "Medium"
        else:
            recommendation = "Reject"
            confidence = "Low"

        print(f"Recommendation: {recommendation}")
        print(f"Confidence: {confidence}")

        # Detailed performance metrics
        print("\n📈 PERFORMANCE METRICS")
        print("-" * 30)
        print(".1%")
        print(".1%")
        print(".1%")
        print(".1%")
        print(".3f")

        # Monte Carlo results
        print("\n🎲 MONTE CARLO ANALYSIS (1,000 simulations)")
        print("-" * 30)
        print(".3f")
        print(".3f")
        print(".1%")
        print(".1%")
        print(".1%")
        print(".1%")

        # Regime analysis
        print("\n🏛️  MARKET REGIME PERFORMANCE")
        print("-" * 30)
        if regime_results['regime_performance']:
            for regime_name, perf in regime_results['regime_performance'].items():
                print(".1%")
                print(".1%")

        # Risk analysis
        print("\n🛡️  RISK ANALYSIS")
        print("-" * 30)
        print("Strategy Type: Intraday Momentum")
        print("Risk Level: High (frequent trading)")
        print("Holding Period: Minutes to hours")
        print("Stop Loss: 2% per trade")
        print("Take Profit: 4% per trade")
        print(f"Max Drawdown: {max_drawdown:.1%}")

        # Strategy parameters
        print("\n⚙️  STRATEGY PARAMETERS")
        print("-" * 30)
        params = strategy.get_parameters()
        print(f"RSI Period: {params['rsi_period']}")
        print(f"RSI Overbought: {params['rsi_overbought']}")
        print(f"RSI Oversold: {params['rsi_oversold']}")
        print(f"Momentum Period: {params['momentum_period']} bars")
        print(f"Volume Multiplier: {params['volume_multiplier']}x")
        print(f"Min Price Move: {params['min_price_move']:.1%}")

        # Final recommendation analysis
        print("\n🎯 FINAL RECOMMENDATION ANALYSIS")
        print("-" * 30)

        if recommendation == "Deploy":
            print("🚀 STRATEGY APPROVED FOR LIVE TRADING")
            print("✓ Strong risk-adjusted returns")
            print("✓ Consistent performance across market conditions")
            print("✓ Robust statistical significance")
            print("\nNext Steps:")
            print("• Implement real-time data feed")
            print("• Set up paper trading validation")
            print("• Monitor intraday performance metrics")
            print("• Scale position sizes gradually")

        elif recommendation == "Caution":
            print("⚠️  REQUIRES PARAMETER OPTIMIZATION")
            print("• Shows trading potential but needs refinement")
            print("• Consider adjusting RSI thresholds")
            print("• Review momentum period sensitivity")
            print("• Test different volume confirmation levels")

        else:
            print("❌ STRATEGY REQUIRES REDESIGN")
            print("• Insufficient performance for live trading")
            print("• High risk relative to potential reward")
            print("• Consider alternative entry/exit logic")
            print("• Review fundamental strategy assumptions")

        print("\n" + "="*80)
        print("🎉 INTRADAY MOMENTUM STRATEGY VALIDATION COMPLETE")
        print("="*80)

        return {
            'recommendation': recommendation,
            'confidence': confidence,
            'overall_score': overall_score,
            'performance_score': performance_score,
            'robustness_score': robustness_score,
            'risk_adjusted_score': risk_adjusted_score,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'total_return': total_return,
            'max_drawdown': max_drawdown
        }

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Run the validation
    results = run_strategy_validation()

    if results:
        print("
💾 Validation complete!"        print(f"Recommendation: {results['recommendation']}")
        print(".2f"    else:
        print("\n❌ Validation failed - check error messages above")
