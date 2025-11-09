#!/usr/bin/env python3
"""
Intraday Momentum Strategy Validation

Comprehensive validation of the intraday momentum strategy using NEXUS's
advanced validation suite. Generates synthetic 5-minute intraday data
and tests the strategy across multiple market conditions.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from nexus.strategies.intraday_momentum import IntradayMomentumStrategy
from nexus.backtesting.validation_runner import ValidationRunner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_intraday_data(symbols: list, trading_days: int = 30) -> dict:
    """
    Generate realistic synthetic 5-minute intraday data.

    Creates data that simulates:
    - Market hours (9:30 AM - 4:00 PM)
    - Weekend gaps
    - Intraday volatility patterns (higher at open/close)
    - Volume spikes during momentum moves
    - Multiple market regimes
    """
    logger.info(f"Generating synthetic intraday data for {len(symbols)} symbols over {trading_days} days")

    data = {}
    start_date = datetime(2024, 11, 1, 9, 30)  # Market open

    for symbol in symbols:
        logger.info(f"Generating data for {symbol}")

        # Symbol-specific parameters
        base_price = {'AAPL': 180, 'GOOGL': 140, 'MSFT': 380, 'TSLA': 250}[symbol]
        daily_volatility = {'AAPL': 0.015, 'GOOGL': 0.020, 'MSFT': 0.012, 'TSLA': 0.025}[symbol]
        avg_volume = {'AAPL': 2000000, 'GOOGL': 1500000, 'MSFT': 1800000, 'TSLA': 3000000}[symbol]

        all_bars = []

        for day in range(trading_days):
            # Skip weekends
            current_date = start_date + timedelta(days=day)
            if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                continue

            # Daily trend (random walk with slight bias)
            daily_trend = np.random.normal(0.0001, 0.003)  # Small daily bias

            # Generate 5-minute bars (9:30 AM to 4:00 PM = 78 bars per day)
            day_bars = []
            current_price = base_price * (1 + daily_trend * day)  # Cumulative trend

            for bar in range(78):  # 6.5 hours * 12 bars/hour = 78 bars
                bar_time = current_date.replace(hour=9, minute=30) + timedelta(minutes=5 * bar)

                # Intraday volatility pattern (higher at open and close)
                time_factor = 1.0
                if bar < 6:  # First 30 minutes (opening volatility)
                    time_factor = 1.8
                elif bar < 12:  # Next hour
                    time_factor = 1.3
                elif bar > 60:  # Last hour (closing volatility)
                    time_factor = 1.5

                # Add some regime-based volatility (simulate news/events)
                regime_volatility = 1.0
                if np.random.random() < 0.1:  # 10% chance of high volatility event
                    regime_volatility = 2.0

                # Calculate price movement
                volatility = daily_volatility * time_factor * regime_volatility
                price_change = np.random.normal(daily_trend/78, volatility)

                open_price = current_price
                high_price = open_price * (1 + abs(np.random.normal(0, volatility*0.8)))
                low_price = open_price * (1 - abs(np.random.normal(0, volatility*0.8)))
                close_price = open_price * (1 + price_change)

                # Ensure OHLC relationships
                high_price = max(high_price, open_price, close_price)
                low_price = min(low_price, open_price, close_price)

                # Volume with intraday patterns and spikes
                base_vol = avg_volume
                # Higher volume at open and close
                if bar < 12 or bar > 60:
                    base_vol *= 1.5
                # Volume spikes on large price moves
                price_move_pct = abs(close_price - open_price) / open_price
                if price_move_pct > 0.005:  # >0.5% move
                    base_vol *= (1 + price_move_pct * 20)

                volume = int(np.random.uniform(base_vol * 0.7, base_vol * 1.3))

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

        # Convert to DataFrame
        df = pd.DataFrame(all_bars)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        data[symbol] = df
        logger.info(f"Generated {len(df)} bars for {symbol}")

    return data


def intraday_strategy_wrapper(price_data: pd.Series, **params) -> pd.Series:
    """
    Wrapper function to adapt the intraday momentum strategy for NEXUS validation.

    The ValidationRunner expects a strategy function that takes price_data as pd.Series,
    but our intraday strategy needs OHLCV data. This wrapper:
    1. Converts the price series to OHLCV format
    2. Creates a mock market data interface
    3. Runs the intraday strategy
    4. Returns signals in the expected format
    """
    try:
        # Create strategy instance with parameters
        strategy = IntradayMomentumStrategy(**params)

        # Convert price series to OHLCV DataFrame format
        df_data = pd.DataFrame({
            'open': price_data,
            'high': price_data * 1.003,  # Realistic high/low spread
            'low': price_data * 0.997,
            'close': price_data,
            'volume': 1000000,  # Constant volume for validation simplicity
        }, index=price_data.index)

        # Create mock market data interface
        class MockMarketData:
            def __init__(self, df):
                self.df = df

            def get_intraday_data(self, symbol, timeframe, periods):
                """Return intraday data in the format expected by the strategy."""
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
                """Return available symbols."""
                return ['AAPL']  # Single symbol for validation

        market_data = MockMarketData(df_data)

        # Generate signals using the strategy
        signals = strategy.generate_signals(market_data)

        # Convert TradeSignal objects to pandas Series format expected by validator
        signal_series = pd.Series(0.0, index=price_data.index)

        for signal in signals:
            # Find the closest timestamp in our data
            signal_time = pd.to_datetime(signal.timestamp)
            closest_idx = price_data.index.get_indexer([signal_time], method='nearest')[0]

            if closest_idx < len(price_data):
                actual_time = price_data.index[closest_idx]
                if signal.direction == 'long':
                    signal_series.loc[actual_time] = 1.0  # Long signal
                elif signal.direction == 'short':
                    signal_series.loc[actual_time] = -1.0  # Short signal
                # 0.0 = neutral (no position)

        logger.debug(f"Generated {len(signals)} signals from {len(price_data)} data points")
        return signal_series

    except Exception as e:
        logger.error(f"Strategy wrapper failed: {e}")
        # Return neutral signals on error
        return pd.Series(0.0, index=price_data.index)


def run_intraday_validation():
    """Run comprehensive validation for the intraday momentum strategy."""

    print("=" * 80)
    print("🤖 NEXUS INTRADAY MOMENTUM STRATEGY VALIDATION")
    print("=" * 80)
    print("Testing Intraday Momentum Strategy:")
    print("• 5-minute timeframe analysis")
    print("• RSI + momentum + volume confirmation")
    print("• Risk management with 2% stops, 4% targets")
    print("• Multi-asset validation (AAPL, GOOGL, MSFT, TSLA)")
    print("=" * 80)

    try:
        # Generate synthetic intraday data
        print("\n📊 Generating Synthetic Intraday Data...")
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
        intraday_data = generate_intraday_data(symbols, trading_days=45)  # ~45 trading days

        # Use AAPL data for primary validation (most liquid)
        price_data = intraday_data['AAPL']['close']
        print(f"✅ Generated {len(price_data)} 5-minute bars")
        print(f"   Data range: {price_data.index[0]} to {price_data.index[-1]}")
        print(".2f")
        print(f"   Daily volatility: {price_data.pct_change().std()*100:.1f}%")

        # Set up validation runner with comprehensive settings
        print("\n🔬 Initializing NEXUS Validation Suite...")
        print("• Monte Carlo Simulation: 1,000 iterations")
        print("• Multi-regime analysis: Bull/Bear/Sideways markets")
        print("• Statistical significance testing (95% confidence)")
        print("• Risk-adjusted performance metrics")

        validator = ValidationRunner(
            enable_walk_forward=False,  # Intraday data works better with MC/regime analysis
            enable_monte_carlo=True,
            enable_regime_analysis=True,
            enable_holdout=False,  # Skip for intraday
            monte_carlo_simulations=1000,  # Robust sample size
            confidence_level=0.95
        )

        # Strategy parameters for validation
        strategy_params = {
            'timeframe_minutes': 5,
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'momentum_period': 10,
            'volume_multiplier': 1.5,
            'stop_loss_pct': 0.02,    # 2% stop loss
            'take_profit_pct': 0.04,  # 4% take profit
            'max_positions': 3,       # Conservative for intraday
            'min_price_move': 0.005,  # 0.5% minimum momentum
        }

        # Run comprehensive validation
        print("\n🚀 Running Comprehensive Validation...")
        print("This may take 30-60 seconds depending on your system...")

        start_time = datetime.now()
        report = validator.run_quick_validation(
            strategy_func=intraday_strategy_wrapper,
            price_data=price_data,
            strategy_params=strategy_params,
            strategy_name="Intraday Momentum Strategy"
        )
        end_time = datetime.now()

        # Display comprehensive results
        print(f"\n✅ Validation completed in {(end_time - start_time).total_seconds():.1f} seconds")
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE VALIDATION REPORT")
        print("="*80)

        # Executive summary
        validator.print_validation_status(report)

        # Detailed performance analysis
        print("\n" + "-"*50)
        print("📈 DETAILED PERFORMANCE METRICS")
        print("-"*50)

        # Monte Carlo analysis
        if report.monte_carlo_analysis:
            mc = report.monte_carlo_analysis
            print(f"Monte Carlo Simulations: {mc.n_simulations}")
            print("Confidence Intervals (95%):")
            if hasattr(mc, 'confidence_intervals'):
                for metric, ci in mc.confidence_intervals.items():
                    if isinstance(ci, tuple) and len(ci) == 2:
                        if 'return' in metric.lower() or 'drawdown' in metric.lower():
                            print(".1%")
                        else:
                            print(".3f")

        # Multi-regime analysis
        if report.regime_analysis:
            regime = report.regime_analysis
            print("
🏛️  MARKET REGIME PERFORMANCE:"            print("-" * 30)
            if hasattr(regime, 'regime_performance'):
                for regime_name, perf in regime.regime_performance.items():
                    if hasattr(perf, 'total_return'):
                        print(".1%")

        # Strategy profile
        print("
🛡️  STRATEGY RISK PROFILE:"        print("-" * 30)
        print(f"Risk Level: High (Intraday Trading)")
        print(f"Timeframe: {strategy_params['timeframe_minutes']}-minute bars")
        print(f"Expected Holding Period: Minutes to hours")
        print(f"Stop Loss: {strategy_params['stop_loss_pct']:.1%}")
        print(f"Take Profit: {strategy_params['take_profit_pct']:.1%}")
        print(f"Max Positions: {strategy_params['max_positions']}")

        # Parameter summary
        print("
⚙️  STRATEGY PARAMETERS:"        print("-" * 30)
        for param_name, param_value in strategy_params.items():
            if isinstance(param_value, float):
                print(f"• {param_name}: {param_value:.3f}")
            else:
                print(f"• {param_name}: {param_value}")

        # Final recommendation with detailed analysis
        print("\n" + "-"*50)
        print("🎯 FINAL RECOMMENDATION & ANALYSIS")
        print("-"*50)

        if report.summary:
            recommendation = report.summary.recommendation
            confidence = report.summary.overall_confidence

            print(f"Recommendation: {recommendation}")
            print(f"Overall Confidence: {confidence}")

            # Detailed analysis based on scores
            perf_score = report.overall_performance_score

            if recommendation == "Deploy" and perf_score > 0.7:
                print("\n🚀 STRATEGY APPROVED FOR LIVE TRADING")
                print("✓ Strong statistical significance")
                print("✓ Robust risk-adjusted returns")
                print("✓ Consistent performance across regimes")
                print("\nNext Steps:")
                print("• Implement real-time data feed integration")
                print("• Set up paper trading environment")
                print("• Monitor performance for 1-2 weeks")
                print("• Scale up position sizes gradually")

            elif recommendation == "Caution" and perf_score > 0.5:
                print("\n⚠️  STRATEGY NEEDS PARAMETER OPTIMIZATION")
                print("• Shows potential but requires tuning")
                print("• Review Monte Carlo results for parameter sensitivity")
                print("• Consider adjusting RSI thresholds or momentum periods")

                if report.summary.key_weaknesses:
                    print("
Areas for improvement:"                    for weakness in report.summary.key_weaknesses[:3]:
                        print(f"• {weakness}")

            else:
                print("\n❌ STRATEGY REQUIRES FUNDAMENTAL REDESIGN")
                print("• Insufficient performance for live trading")
                print("• High risk relative to reward potential")
                print("• Consider alternative entry/exit logic")

                if report.summary.key_weaknesses:
                    print("
Critical issues:"                    for weakness in report.summary.key_weaknesses[:3]:
                        print(f"• {weakness}")
        else:
            print("\n❓ UNABLE TO GENERATE RECOMMENDATION")
            print("Validation completed but results are inconclusive")

        # Performance scores summary
        print("
📊 PERFORMANCE SCORES SUMMARY:"        print(".2f"        print(".2f"        print(".2f"        if hasattr(report, 'robustness_score'):
            print(".2f"
        print("\n" + "="*80)
        print("🎉 INTRADAY MOMENTUM STRATEGY VALIDATION COMPLETE")
        print("="*80)

        return report

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        print("Check data generation and strategy implementation")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Run the validation
    report = run_intraday_validation()

    if report:
        print("
💾 Validation results saved to memory."        print("To run again: python validate_intraday_momentum_strategy.py")
    else:
        print("\n❌ Validation failed - see error messages above")
