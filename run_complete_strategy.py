#!/usr/bin/env python3
"""
Complete Strategy Test Run

Tests multiple trading strategies using real market data from the API.
"""

import requests
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"


class StrategyRunner:
    """Run trading strategies using API data."""

    def __init__(self):
        self.results = {}
        self.data_cache = {}

    def fetch_data(self, symbol: str, days: int = 90) -> pd.DataFrame:
        """Fetch historical data from API."""
        if symbol in self.data_cache:
            return self.data_cache[symbol]

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            params = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }

            response = requests.get(
                f"{BASE_URL}/api/v1/historical/{symbol}",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get("data", [])

                if records:
                    df = pd.DataFrame(records)
                    # Clean up column names
                    df.columns = [col.title() if col.islower() else col for col in df.columns]
                    self.data_cache[symbol] = df
                    return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")

        return pd.DataFrame()

    def strategy_golden_cross(self, symbol: str = "AAPL"):
        """Golden Cross Strategy: MA20 crosses above MA50."""
        logger.info("\n" + "="*80)
        logger.info(f"STRATEGY 1: GOLDEN CROSS - {symbol}")
        logger.info("="*80)

        try:
            df = self.fetch_data(symbol, days=180)

            if df.empty:
                logger.warning("No data available")
                self.results['Golden Cross'] = {'status': 'FAILED', 'reason': 'No data'}
                return

            logger.info(f"✓ Fetched {len(df)} candles for {symbol}")

            # Calculate moving averages
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA50'] = df['Close'].rolling(window=50).mean()

            # Generate signals
            signals = []
            for i in range(50, len(df)):
                if df['MA20'].iloc[i] > df['MA50'].iloc[i] and \
                   df['MA20'].iloc[i-1] <= df['MA50'].iloc[i-1]:
                    signals.append({
                        'type': 'BUY',
                        'date': str(df.index[i] if hasattr(df.index, '__getitem__') else i),
                        'price': float(df['Close'].iloc[i])
                    })
                elif df['MA20'].iloc[i] < df['MA50'].iloc[i] and \
                     df['MA20'].iloc[i-1] >= df['MA50'].iloc[i-1]:
                    signals.append({
                        'type': 'SELL',
                        'date': str(df.index[i] if hasattr(df.index, '__getitem__') else i),
                        'price': float(df['Close'].iloc[i])
                    })

            logger.info(f"✓ Generated {len(signals)} trading signals")

            # Calculate performance
            trades = []
            for i in range(0, len(signals) - 1, 2):
                if signals[i]['type'] == 'BUY' and i + 1 < len(signals):
                    buy_price = signals[i]['price']
                    sell_price = signals[i+1]['price']
                    ret = (sell_price - buy_price) / buy_price
                    trades.append({
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'return': ret
                    })

            if trades:
                returns = [t['return'] for t in trades]
                win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
                avg_return = np.mean(returns)
                total_return = np.sum(returns)

                logger.info(f"\n  Trading Performance:")
                logger.info(f"    Total Trades: {len(trades)}")
                logger.info(f"    Winning Trades: {sum(1 for r in returns if r > 0)}")
                logger.info(f"    Win Rate: {win_rate:.1f}%")
                logger.info(f"    Avg Return per Trade: {avg_return*100:.2f}%")
                logger.info(f"    Total Return: {total_return*100:.2f}%")

                self.results['Golden Cross'] = {
                    'status': 'PASSED',
                    'symbol': symbol,
                    'candles': len(df),
                    'signals': len(signals),
                    'trades': len(trades),
                    'win_rate': win_rate,
                    'avg_return': avg_return,
                    'total_return': total_return
                }
            else:
                logger.info("  No completed trades")
                self.results['Golden Cross'] = {
                    'status': 'PASSED',
                    'symbol': symbol,
                    'candles': len(df),
                    'signals': len(signals),
                    'trades': 0
                }

        except Exception as e:
            logger.error(f"✗ Error: {e}")
            self.results['Golden Cross'] = {'status': 'FAILED', 'reason': str(e)}

    def strategy_rsi_extreme(self, symbol: str = "GOOGL"):
        """RSI Extreme Strategy: Trade RSI oversold/overbought."""
        logger.info("\n" + "="*80)
        logger.info(f"STRATEGY 2: RSI EXTREMES - {symbol}")
        logger.info("="*80)

        try:
            df = self.fetch_data(symbol, days=120)

            if df.empty:
                logger.warning("No data available")
                self.results['RSI Extremes'] = {'status': 'FAILED', 'reason': 'No data'}
                return

            logger.info(f"✓ Fetched {len(df)} candles for {symbol}")

            # Calculate RSI
            period = 14
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # Find extremes
            oversold = sum(1 for x in df['RSI'] if x < 30)
            overbought = sum(1 for x in df['RSI'] if x > 70)

            # Calculate recovery from extremes
            recoveries = 0
            for i in range(1, len(df)):
                if df['RSI'].iloc[i-1] < 30 and df['RSI'].iloc[i] > 35:
                    recoveries += 1
                elif df['RSI'].iloc[i-1] > 70 and df['RSI'].iloc[i] < 65:
                    recoveries += 1

            logger.info(f"\n  RSI Analysis:")
            logger.info(f"    Current RSI: {df['RSI'].iloc[-1]:.2f}")
            logger.info(f"    RSI Range: {df['RSI'].min():.2f} - {df['RSI'].max():.2f}")
            logger.info(f"    Oversold Periods: {oversold}")
            logger.info(f"    Overbought Periods: {overbought}")
            logger.info(f"    Mean Reversions Detected: {recoveries}")

            self.results['RSI Extremes'] = {
                'status': 'PASSED',
                'symbol': symbol,
                'candles': len(df),
                'oversold': oversold,
                'overbought': overbought,
                'reversions': recoveries,
                'rsi_current': float(df['RSI'].iloc[-1])
            }

        except Exception as e:
            logger.error(f"✗ Error: {e}")
            self.results['RSI Extremes'] = {'status': 'FAILED', 'reason': str(e)}

    def strategy_bollinger_bands(self, symbol: str = "MSFT"):
        """Bollinger Bands Strategy: Trade mean reversion."""
        logger.info("\n" + "="*80)
        logger.info(f"STRATEGY 3: BOLLINGER BANDS - {symbol}")
        logger.info("="*80)

        try:
            df = self.fetch_data(symbol, days=150)

            if df.empty:
                logger.warning("No data available")
                self.results['Bollinger Bands'] = {'status': 'FAILED', 'reason': 'No data'}
                return

            logger.info(f"✓ Fetched {len(df)} candles for {symbol}")

            # Calculate Bollinger Bands
            period = 20
            df['SMA'] = df['Close'].rolling(window=period).mean()
            df['STD'] = df['Close'].rolling(window=period).std()
            df['Upper'] = df['SMA'] + (df['STD'] * 2)
            df['Lower'] = df['SMA'] - (df['STD'] * 2)

            # Count touches
            upper_touches = 0
            lower_touches = 0
            for i in range(period, len(df)):
                if pd.notna(df['Upper'].iloc[i]) and df['Close'].iloc[i] >= df['Upper'].iloc[i]:
                    upper_touches += 1
                if pd.notna(df['Lower'].iloc[i]) and df['Close'].iloc[i] <= df['Lower'].iloc[i]:
                    lower_touches += 1

            # Calculate squeeze periods
            df['BBW'] = df['Upper'] - df['Lower']
            squeeze_threshold = df['BBW'].quantile(0.25)
            squeeze_periods = sum(1 for x in df['BBW'] if x < squeeze_threshold)

            current_price = df['Close'].iloc[-1]
            current_sma = df['SMA'].iloc[-1]
            current_upper = df['Upper'].iloc[-1]
            current_lower = df['Lower'].iloc[-1]
            current_bbw = df['BBW'].iloc[-1]

            logger.info(f"\n  Bollinger Bands Analysis:")
            logger.info(f"    Current Price: {current_price:.2f}")
            logger.info(f"    Current SMA: {current_sma:.2f}")
            logger.info(f"    Band Width: {current_bbw:.2f}")
            logger.info(f"    Upper Band: {current_upper:.2f}")
            logger.info(f"    Lower Band: {current_lower:.2f}")
            logger.info(f"    Upper Band Touches: {upper_touches}")
            logger.info(f"    Lower Band Touches: {lower_touches}")
            logger.info(f"    Squeeze Periods: {squeeze_periods}")

            self.results['Bollinger Bands'] = {
                'status': 'PASSED',
                'symbol': symbol,
                'candles': len(df),
                'upper_touches': upper_touches,
                'lower_touches': lower_touches,
                'squeeze_periods': squeeze_periods,
                'current_bbw': float(current_bbw)
            }

        except Exception as e:
            logger.error(f"✗ Error: {e}")
            self.results['Bollinger Bands'] = {'status': 'FAILED', 'reason': str(e)}

    def strategy_ema_crossover(self, symbol: str = "TSLA"):
        """EMA Crossover Strategy: Fast EMA crosses Slow EMA."""
        logger.info("\n" + "="*80)
        logger.info(f"STRATEGY 4: EMA CROSSOVER - {symbol}")
        logger.info("="*80)

        try:
            df = self.fetch_data(symbol, days=200)

            if df.empty:
                logger.warning("No data available")
                self.results['EMA Crossover'] = {'status': 'FAILED', 'reason': 'No data'}
                return

            logger.info(f"✓ Fetched {len(df)} candles for {symbol}")

            # Calculate EMAs
            df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            # Find crossovers
            buy_signals = 0
            sell_signals = 0
            for i in range(1, len(df)):
                if df['MACD'].iloc[i] > df['Signal'].iloc[i] and \
                   df['MACD'].iloc[i-1] <= df['Signal'].iloc[i-1]:
                    buy_signals += 1
                elif df['MACD'].iloc[i] < df['Signal'].iloc[i] and \
                     df['MACD'].iloc[i-1] >= df['Signal'].iloc[i-1]:
                    sell_signals += 1

            current_trend = "BULLISH" if df['EMA12'].iloc[-1] > df['EMA26'].iloc[-1] else "BEARISH"
            macd_trend = "POSITIVE" if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] else "NEGATIVE"

            logger.info(f"\n  MACD Analysis:")
            logger.info(f"    EMA12: {df['EMA12'].iloc[-1]:.2f}")
            logger.info(f"    EMA26: {df['EMA26'].iloc[-1]:.2f}")
            logger.info(f"    MACD: {df['MACD'].iloc[-1]:.4f}")
            logger.info(f"    Signal: {df['Signal'].iloc[-1]:.4f}")
            logger.info(f"    Buy Signals: {buy_signals}")
            logger.info(f"    Sell Signals: {sell_signals}")
            logger.info(f"    Current Trend: {current_trend}")
            logger.info(f"    MACD Trend: {macd_trend}")

            self.results['EMA Crossover'] = {
                'status': 'PASSED',
                'symbol': symbol,
                'candles': len(df),
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'current_trend': current_trend,
                'macd_trend': macd_trend
            }

        except Exception as e:
            logger.error(f"✗ Error: {e}")
            self.results['EMA Crossover'] = {'status': 'FAILED', 'reason': str(e)}

    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("STRATEGY TEST SUMMARY")
        logger.info("="*80)

        passed = sum(1 for r in self.results.values() if r.get('status') == 'PASSED')
        total = len(self.results)

        for strategy, result in self.results.items():
            status_icon = "✓" if result.get('status') == 'PASSED' else "✗"
            logger.info(f"{status_icon} {strategy:25} - {result.get('status', 'UNKNOWN')}")

            if result.get('status') == 'PASSED':
                logger.info(f"  └─ Candles: {result.get('candles', 'N/A')}")

                if 'trades' in result:
                    logger.info(f"     Trades: {result['trades']}")
                    logger.info(f"     Win Rate: {result.get('win_rate', 0):.1f}%")
                    logger.info(f"     Total Return: {result.get('total_return', 0)*100:.2f}%")

        logger.info("="*80)
        logger.info(f"Summary: {passed}/{total} strategies passed")
        logger.info("="*80 + "\n")

        # Save results
        self._save_results()

        return passed == total

    def _save_results(self):
        """Save results to JSON."""
        output_file = "/Users/stephenlopez/Projects/Trading Projects/nexus/new_project/strategy_results.json"

        data = {
            'timestamp': datetime.now().isoformat(),
            'results': self.results,
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results.values() if r.get('status') == 'PASSED'),
                'success_rate': (sum(1 for r in self.results.values() if r.get('status') == 'PASSED') / len(self.results) * 100) if self.results else 0
            }
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to: strategy_results.json")

    def run(self):
        """Run all strategies."""
        logger.info("\n")
        logger.info("╔" + "="*78 + "╗")
        logger.info("║" + " NEXUS COMPLETE STRATEGY TEST RUN".center(78) + "║")
        logger.info("║" + f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(78) + "║")
        logger.info("╚" + "="*78 + "╝")

        # Run strategies
        self.strategy_golden_cross("AAPL")
        self.strategy_rsi_extreme("GOOGL")
        self.strategy_bollinger_bands("MSFT")
        self.strategy_ema_crossover("TSLA")

        # Print summary
        success = self.print_summary()

        return success


if __name__ == "__main__":
    runner = StrategyRunner()
    success = runner.run()
    exit(0 if success else 1)
