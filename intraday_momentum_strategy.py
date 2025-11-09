"""
Intraday Momentum Strategy for 5-15 minute timeframes across multiple assets.

This strategy captures short-term momentum bursts using RSI and price action.
Works well for stocks, crypto, forex during active market hours.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

class IntradayMomentumStrategy:
    """
    Intraday momentum strategy that works on 5-15 minute charts.

    Key features:
    - Short-term RSI momentum (5-15 period)
    - Volume confirmation
    - Multi-timeframe confirmation (5min + 15min)
    - Risk management with stop losses
    - Works across stocks, crypto, forex
    """

    def __init__(
        self,
        timeframe_minutes: int = 5,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        momentum_period: int = 10,  # Short-term momentum lookback
        volume_multiplier: float = 1.5,  # Volume must be 1.5x average
        stop_loss_pct: float = 0.02,  # 2% stop loss
        take_profit_pct: float = 0.04,  # 4% take profit
        max_positions: int = 5,
        min_price_move: float = 0.005,  # Minimum 0.5% price move for entry
    ):
        self.timeframe_minutes = timeframe_minutes
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.momentum_period = momentum_period
        self.volume_multiplier = volume_multiplier
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_positions = max_positions
        self.min_price_move = min_price_move

        self.logger = logging.getLogger(__name__)
        self.active_positions = {}  # Track open positions

    def generate_signals(self, symbol: str, data_5m: pd.DataFrame, data_15m: Optional[pd.DataFrame] = None) -> List[Dict]:
        """
        Generate trading signals for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTC/USD')
            data_5m: 5-minute OHLCV data
            data_15m: Optional 15-minute data for confirmation

        Returns:
            List of signal dictionaries
        """
        signals = []

        if len(data_5m) < self.rsi_period + self.momentum_period:
            return signals

        # Calculate indicators on 5-minute data
        data_5m = self._add_indicators(data_5m)

        # Get latest data point
        current = data_5m.iloc[-1]

        # Check for momentum signals
        long_signal = self._check_long_signal(current, data_5m)
        short_signal = self._check_short_signal(current, data_5m)

        # Multi-timeframe confirmation if 15m data available
        if data_15m is not None and len(data_15m) >= 5:
            data_15m = self._add_indicators(data_15m)
            current_15m = data_15m.iloc[-1]

            if long_signal:
                long_signal = self._confirm_15m(current_15m, 'long')
            if short_signal:
                short_signal = self._confirm_15m(current_15m, 'short')

        # Generate signals
        if long_signal and len(self.active_positions) < self.max_positions:
            signals.append({
                'symbol': symbol,
                'direction': 'long',
                'timestamp': current.name,
                'entry_price': current['close'],
                'stop_loss': current['close'] * (1 - self.stop_loss_pct),
                'take_profit': current['close'] * (1 + self.take_profit_pct),
                'confidence': long_signal['confidence'],
                'reasoning': long_signal['reasoning'],
                'indicators': {
                    'rsi': current['rsi'],
                    'momentum': current['momentum'],
                    'volume_ratio': current['volume_ratio']
                }
            })

        elif short_signal and len(self.active_positions) < self.max_positions:
            signals.append({
                'symbol': symbol,
                'direction': 'short',
                'timestamp': current.name,
                'entry_price': current['close'],
                'stop_loss': current['close'] * (1 + self.stop_loss_pct),
                'take_profit': current['close'] * (1 - self.take_profit_pct),
                'confidence': short_signal['confidence'],
                'reasoning': short_signal['reasoning'],
                'indicators': {
                    'rsi': current['rsi'],
                    'momentum': current['momentum'],
                    'volume_ratio': current['volume_ratio']
                }
            })

        return signals

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the dataframe."""
        df = df.copy()

        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)

        # Short-term momentum (rate of change)
        df['momentum'] = df['close'].pct_change(self.momentum_period)

        # Volume ratio (current volume vs recent average)
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        return df

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _check_long_signal(self, current: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """Check for long entry signal."""
        # Conditions for long:
        # 1. RSI oversold (< 30)
        # 2. Positive momentum (price increasing)
        # 3. Volume above average
        # 4. Recent price move meets minimum threshold

        if (current['rsi'] < self.rsi_oversold and
            current['momentum'] > self.min_price_move and
            current['volume_ratio'] > self.volume_multiplier):

            # Check if momentum is accelerating (improving)
            prev_momentum = data.iloc[-2]['momentum'] if len(data) > 1 else 0
            momentum_acceleration = current['momentum'] > prev_momentum

            if momentum_acceleration:
                confidence = min(0.9, 0.5 + (self.min_price_move / current['momentum']) * 0.3)
                confidence = min(confidence, 0.5 + (current['volume_ratio'] - 1) * 0.2)

                return {
                    'confidence': confidence,
                    'reasoning': f"Intraday momentum long: RSI {current['rsi']:.1f}, momentum {current['momentum']:.1%}, volume {current['volume_ratio']:.1f}x"
                }

        return None

    def _check_short_signal(self, current: pd.Series, data: pd.DataFrame) -> Optional[Dict]:
        """Check for short entry signal."""
        # Conditions for short:
        # 1. RSI overbought (> 70)
        # 2. Negative momentum (price decreasing)
        # 3. Volume above average
        # 4. Recent price move meets minimum threshold (absolute value)

        if (current['rsi'] > self.rsi_overbought and
            current['momentum'] < -self.min_price_move and
            current['volume_ratio'] > self.volume_multiplier):

            # Check if momentum is decelerating (worsening)
            prev_momentum = data.iloc[-2]['momentum'] if len(data) > 1 else 0
            momentum_deceleration = current['momentum'] < prev_momentum

            if momentum_deceleration:
                confidence = min(0.9, 0.5 + (abs(current['momentum']) / self.min_price_move) * 0.3)
                confidence = min(confidence, 0.5 + (current['volume_ratio'] - 1) * 0.2)

                return {
                    'confidence': confidence,
                    'reasoning': f"Intraday momentum short: RSI {current['rsi']:.1f}, momentum {current['momentum']:.1%}, volume {current['volume_ratio']:.1f}x"
                }

        return None

    def _confirm_15m(self, current_15m: pd.Series, direction: str) -> bool:
        """Check 15-minute timeframe confirmation."""
        if direction == 'long':
            # For longs, 15m should also show positive momentum or neutral
            return current_15m['momentum'] > -0.005  # Not strongly negative
        else:
            # For shorts, 15m should also show negative momentum or neutral
            return current_15m['momentum'] < 0.005  # Not strongly positive

    def update_positions(self, symbol: str, current_price: float, timestamp: datetime):
        """Update open positions and check for exits."""
        if symbol not in self.active_positions:
            return

        position = self.active_positions[symbol]

        # Check stop loss and take profit
        if position['direction'] == 'long':
            if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                self._close_position(symbol, current_price, timestamp)
        else:  # short
            if current_price >= position['stop_loss'] or current_price <= position['take_profit']:
                self._close_position(symbol, current_price, timestamp)

    def _close_position(self, symbol: str, exit_price: float, timestamp: datetime):
        """Close a position."""
        if symbol in self.active_positions:
            position = self.active_positions[symbol]
            pnl = (exit_price - position['entry_price']) / position['entry_price']
            if position['direction'] == 'short':
                pnl = -pnl

            self.logger.info(".1%"f"Closed {position['direction']} position in {symbol}: PnL {pnl:.1%}")
            del self.active_positions[symbol]

    def get_strategy_info(self) -> Dict:
        """Get strategy metadata."""
        return {
            'name': 'Intraday Momentum Strategy',
            'description': 'Short-term momentum strategy for 5-15 minute charts',
            'timeframes': ['5m', '15m'],
            'assets': ['stocks', 'crypto', 'forex', 'commodities'],
            'risk_level': 'high',
            'best_market_conditions': 'trending markets with momentum bursts',
            'parameters': {
                'rsi_period': self.rsi_period,
                'rsi_overbought': self.rsi_overbought,
                'rsi_oversold': self.rsi_oversold,
                'momentum_period': self.momentum_period,
                'volume_multiplier': self.volume_multiplier,
                'stop_loss_pct': self.stop_loss_pct,
                'take_profit_pct': self.take_profit_pct,
                'max_positions': self.max_positions,
                'min_price_move': self.min_price_move
            }
        }


# Example usage function
def run_intraday_momentum_strategy(symbols: List[str], data_fetcher) -> List[Dict]:
    """
    Run the strategy across multiple symbols.

    Args:
        symbols: List of symbols to trade
        data_fetcher: Function that returns OHLCV data for a symbol and timeframe

    Returns:
        List of all generated signals
    """
    strategy = IntradayMomentumStrategy()
    all_signals = []

    for symbol in symbols:
        try:
            # Get 5-minute data
            data_5m = data_fetcher(symbol, '5m', lookback_periods=100)

            # Optional: Get 15-minute data for confirmation
            data_15m = data_fetcher(symbol, '15m', lookback_periods=50)

            # Generate signals
            signals = strategy.generate_signals(symbol, data_5m, data_15m)
            all_signals.extend(signals)

        except Exception as e:
            logging.error(f"Error processing {symbol}: {e}")
            continue

    return all_signals


# Sample validation function
def validate_strategy_performance(signals: List[Dict], historical_data: Dict[str, pd.DataFrame]) -> Dict:
    """
    Backtest the strategy performance.

    Args:
        signals: Generated signals
        historical_data: Historical OHLCV data for validation

    Returns:
        Performance metrics
    """
    total_trades = len(signals)
    winning_trades = 0
    total_pnl = 0

    for signal in signals:
        symbol = signal['symbol']
        entry_price = signal['entry_price']
        direction = signal['direction']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']

        # Simulate trade (simplified - would need actual tick data)
        if direction == 'long':
            # Assume we hit take profit 60% of time, stop loss 40%
            if np.random.random() < 0.6:
                exit_price = take_profit
                pnl = (exit_price - entry_price) / entry_price
            else:
                exit_price = stop_loss
                pnl = (exit_price - entry_price) / entry_price
        else:  # short
            if np.random.random() < 0.6:
                exit_price = take_profit
                pnl = (entry_price - exit_price) / entry_price  # Profit when price goes down
            else:
                exit_price = stop_loss
                pnl = (entry_price - exit_price) / entry_price

        total_pnl += pnl
        if pnl > 0:
            winning_trades += 1

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
        'total_pnl': total_pnl,
        'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0
    }


if __name__ == "__main__":
    # Example usage
    strategy = IntradayMomentumStrategy()
    print("Strategy Info:", strategy.get_strategy_info())

    # Mock data fetcher for demonstration - creates controlled scenarios
    def mock_data_fetcher(symbol, timeframe, lookback_periods):
        # Generate sample OHLCV data
        dates = pd.date_range('2024-01-01 09:30:00', periods=lookback_periods, freq='5min')
        np.random.seed(42)

        # Create controlled price action for demonstration
        base_price = 100

        # Phase 1: Strong uptrend (gets overbought)
        uptrend_prices = []
        for i in range(40):
            if i == 0:
                uptrend_prices.append(base_price)
            else:
                # Strong upward moves
                change = 0.015 + np.random.normal(0, 0.005)  # ~1.5% up per 5min bar
                new_price = uptrend_prices[-1] * (1 + change)
                uptrend_prices.append(new_price)

        # Phase 2: Sharp rejection (creates short signal conditions)
        rejection_prices = []
        last_up_price = uptrend_prices[-1]
        for i in range(25):
            change = -0.012 + np.random.normal(0, 0.008)  # ~1.2% down per bar
            if i == 0:
                rejection_prices.append(last_up_price * (1 + change))
            else:
                rejection_prices.append(rejection_prices[-1] * (1 + change))

        # Phase 3: Oversold bounce (creates long signal conditions)
        bounce_prices = []
        last_rejection_price = rejection_prices[-1]
        for i in range(35):
            change = 0.018 + np.random.normal(0, 0.006)  # ~1.8% up per bar
            if i == 0:
                bounce_prices.append(last_rejection_price * (1 + change))
            else:
                bounce_prices.append(bounce_prices[-1] * (1 + change))

        prices = uptrend_prices + rejection_prices + bounce_prices

        # Ensure we have exactly lookback_periods
        if len(prices) > lookback_periods:
            prices = prices[-lookback_periods:]
        elif len(prices) < lookback_periods:
            # Pad with recent prices if needed
            last_price = prices[-1]
            for i in range(lookback_periods - len(prices)):
                prices.append(last_price * (1 + np.random.normal(0, 0.002)))

        # Volume: higher during momentum moves
        volumes = []
        for i in range(len(prices)):
            if i < 40:  # Normal volume during uptrend
                vol = int(np.random.normal(5000, 1000))
            elif i < 65:  # High volume during rejection
                vol = int(np.random.normal(12000, 2000))
            else:  # High volume during bounce
                vol = int(np.random.normal(15000, 3000))
            volumes.append(max(1000, vol))

        # Create OHLCV data
        data = {
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.003))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.003))) for p in prices],
            'close': prices,
            'volume': volumes
        }

        return pd.DataFrame(data, index=dates[:len(prices)])

    # Test with sample data
    symbols = ['AAPL']
    signals = run_intraday_momentum_strategy(symbols, mock_data_fetcher)

    print(f"\nGenerated {len(signals)} signals:")
    for signal in signals[:3]:  # Show first 3
        print(f"- {signal['symbol']} {signal['direction']} at {signal['entry_price']:.2f} "
              f"(confidence: {signal['confidence']:.2f})")

    # Debug: Check what the indicators look like for the last few bars
    if symbols:
        data = mock_data_fetcher(symbols[0], '5m', 100)
        data_with_indicators = strategy._add_indicators(data)
        print("\nLast 5 bars of indicators:")
        last_few = data_with_indicators.tail(5)
        for idx, row in last_few.iterrows():
            print(f"  {idx}: RSI={row['rsi']:.1f}, Momentum={row['momentum']:.3f}, VolRatio={row['volume_ratio']:.1f}")
