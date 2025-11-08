"""RSI Divergence trading strategy implementation.

This module implements RSI divergence strategy based on technical analysis research.
RSI divergence signals potential reversals when momentum diverges from price.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

import numpy as np
import pandas as pd

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class RSIDivergenceStrategy(BaseStrategy):
    """RSI divergence strategy for trend reversal detection.

    Based on technical analysis research: RSI divergence occurs when price
    makes a new high/low but RSI fails to confirm, signaling weakening momentum.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        lookback_period: int = 20,
        divergence_threshold: float = 0.5,
        confirmation_period: int = 3,
        max_positions: Optional[int] = None,
        min_price: float = 1.0,
        min_volume: int = 1000,
    ) -> None:
        """Initialize RSI divergence strategy.

        Args:
            rsi_period: Period for RSI calculation
            lookback_period: Days to look back for divergence detection
            divergence_threshold: Minimum divergence magnitude
            confirmation_period: Days to wait for confirmation
            max_positions: Maximum positions per side
            min_price: Minimum stock price filter
            min_volume: Minimum daily volume filter
        """
        super().__init__(
            rsi_period=rsi_period,
            lookback_period=lookback_period,
            divergence_threshold=divergence_threshold,
            confirmation_period=confirmation_period,
            max_positions=max_positions,
            min_price=min_price,
            min_volume=min_volume,
        )

    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        params = self.get_parameters()

        # RSI period
        if not isinstance(params['rsi_period'], int) or params['rsi_period'] < 2:
            raise ParameterError("rsi_period must be integer >= 2")

        # Lookback period
        if not isinstance(params['lookback_period'], int) or params['lookback_period'] < 10:
            raise ParameterError("lookback_period must be integer >= 10")

        # Divergence threshold
        if not isinstance(params['divergence_threshold'], (int, float)) or params['divergence_threshold'] <= 0:
            raise ParameterError("divergence_threshold must be positive")

        # Confirmation period
        if not isinstance(params['confirmation_period'], int) or params['confirmation_period'] < 1:
            raise ParameterError("confirmation_period must be integer >= 1")

        # Max positions
        if params['max_positions'] is not None:
            if not isinstance(params['max_positions'], int) or params['max_positions'] < 1:
                raise ParameterError("max_positions must be positive integer or None")

        # Filters
        if not isinstance(params['min_price'], (int, float)) or params['min_price'] < 0:
            raise ParameterError("min_price must be non-negative")

        if not isinstance(params['min_volume'], int) or params['min_volume'] < 0:
            raise ParameterError("min_volume must be non-negative")

        return True

    @property
    def metadata(self) -> StrategyMetadata:
        """Strategy metadata."""
        return StrategyMetadata(
            name="RSI Divergence Strategy",
            description="Detects trend reversals using RSI divergence from price action",
            version="1.0.0",
            parameters={
                'rsi_period': ParameterSpec(
                    name='rsi_period',
                    type='int',
                    default=14,
                    min_value=2,
                    max_value=30,
                    description="Period for RSI calculation"
                ),
                'lookback_period': ParameterSpec(
                    name='lookback_period',
                    type='int',
                    default=20,
                    min_value=10,
                    max_value=50,
                    description="Days to look back for divergence detection"
                ),
                'divergence_threshold': ParameterSpec(
                    name='divergence_threshold',
                    type='float',
                    default=0.5,
                    min_value=0.1,
                    max_value=2.0,
                    description="Minimum divergence magnitude"
                ),
                'confirmation_period': ParameterSpec(
                    name='confirmation_period',
                    type='int',
                    default=3,
                    min_value=1,
                    max_value=10,
                    description="Days to wait for confirmation"
                ),
                'max_positions': ParameterSpec(
                    name='max_positions',
                    type='int',
                    default=None,
                    min_value=1,
                    description="Maximum positions per side (None = unlimited)"
                ),
                'min_price': ParameterSpec(
                    name='min_price',
                    type='float',
                    default=1.0,
                    min_value=0.0,
                    description="Minimum stock price filter"
                ),
                'min_volume': ParameterSpec(
                    name='min_volume',
                    type='int',
                    default=1000,
                    min_value=0,
                    description="Minimum daily volume filter"
                ),
            },
            risk_profile={
                'strategy_type': 'divergence',
                'horizon': 'short-term',
                'volatility': 'medium',
                'market_regime_sensitivity': 'works in trending and range-bound markets',
                'crash_risk': 'medium (false signals in strong trends)',
            },
            tags=['rsi', 'divergence', 'technical', 'momentum', 'reversal'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 7),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate RSI divergence signals.

        Looks for bullish/bearish divergence between price and RSI.

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals

        Raises:
            SignalError: If signal generation fails
        """
        try:
            params = self.get_parameters()
            rsi_period = params['rsi_period']
            lookback = params['lookback_period']
            threshold = params['divergence_threshold']
            confirmation = params['confirmation_period']

            # Get historical data
            historical_data = market_data.get_historical_data('SPY', lookback + rsi_period + 10)

            if len(historical_data) < lookback + rsi_period:
                return []

            # Extract prices
            prices = [entry['close'] for entry in historical_data]
            prices = [p for p in prices if isinstance(p, (int, float)) and p > 0]

            if len(prices) < lookback + rsi_period:
                return []

            # Calculate RSI
            rsi_values = self._calculate_rsi(prices, rsi_period)

            # Detect divergences
            bullish_divergence = self._detect_bullish_divergence(prices, rsi_values, lookback, threshold)
            bearish_divergence = self._detect_bearish_divergence(prices, rsi_values, lookback, threshold)

            signals = []
            timestamp = datetime.utcnow()

            # Generate signals with confirmation
            if bullish_divergence and self._confirm_signal(prices, confirmation, bullish=True):
                confidence = min(bullish_divergence['strength'] / threshold, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='long',
                    confidence=confidence,
                    reasoning=f"RSI Bullish Divergence: Price low {bullish_divergence['price_low']:.2f}, RSI high {bullish_divergence['rsi_high']:.1f}",
                    metadata={
                        'strategy': 'rsi_divergence',
                        'divergence_type': 'bullish',
                        'rsi_period': rsi_period,
                        'lookback_period': lookback,
                        'divergence_strength': bullish_divergence['strength'],
                        'position_size': 0.02,
                        'max_portfolio_exposure': 0.10
                    }
                )
                signals.append(signal)

            elif bearish_divergence and self._confirm_signal(prices, confirmation, bullish=False):
                confidence = min(bearish_divergence['strength'] / threshold, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='short',
                    confidence=confidence,
                    reasoning=f"RSI Bearish Divergence: Price high {bearish_divergence['price_high']:.2f}, RSI low {bearish_divergence['rsi_low']:.1f}",
                    metadata={
                        'strategy': 'rsi_divergence',
                        'divergence_type': 'bearish',
                        'rsi_period': rsi_period,
                        'lookback_period': lookback,
                        'divergence_strength': bearish_divergence['strength'],
                        'position_size': 0.02,
                        'max_portfolio_exposure': 0.10
                    }
                )
                signals.append(signal)

            return signals

        except Exception as e:
            self._logger.error(f"RSI divergence signal generation failed: {e}")
            raise SignalError(f"Failed to generate RSI divergence signals: {e}") from e

    def _calculate_rsi(self, prices: List[float], period: int) -> List[float]:
        """Calculate RSI values."""
        if len(prices) < period + 1:
            return []

        rsi_values = []
        gains = []
        losses = []

        # Calculate price changes
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        # Calculate initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)

        # Calculate subsequent RSI values
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values

    def _detect_bullish_divergence(self, prices: List[float], rsi_values: List[float],
                                  lookback: int, threshold: float) -> Optional[Dict[str, Any]]:
        """Detect bullish divergence (price lower low, RSI higher low)."""
        if len(prices) < lookback or len(rsi_values) < lookback:
            return None

        # Find recent lows
        recent_prices = prices[-lookback:]
        recent_rsi = rsi_values[-lookback:]

        # Find price low and corresponding RSI
        price_min_idx = recent_prices.index(min(recent_prices))
        rsi_at_price_low = recent_rsi[price_min_idx]

        # Look for earlier low
        earlier_prices = recent_prices[:-5]  # Exclude last 5 days
        if not earlier_prices:
            return None

        earlier_price_min_idx = earlier_prices.index(min(earlier_prices))
        earlier_rsi_at_low = recent_rsi[earlier_price_min_idx]

        # Check for bullish divergence
        price_low = min(recent_prices)
        earlier_price_low = min(earlier_prices)

        if (price_low < earlier_price_low and
            rsi_at_price_low > earlier_rsi_at_low and
            rsi_at_price_low - earlier_rsi_at_low >= threshold):

            return {
                'price_low': price_low,
                'rsi_high': rsi_at_price_low,
                'strength': rsi_at_price_low - earlier_rsi_at_low
            }

        return None

    def _detect_bearish_divergence(self, prices: List[float], rsi_values: List[float],
                                  lookback: int, threshold: float) -> Optional[Dict[str, Any]]:
        """Detect bearish divergence (price higher high, RSI lower high)."""
        if len(prices) < lookback or len(rsi_values) < lookback:
            return None

        # Find recent highs
        recent_prices = prices[-lookback:]
        recent_rsi = rsi_values[-lookback:]

        # Find price high and corresponding RSI
        price_max_idx = recent_prices.index(max(recent_prices))
        rsi_at_price_high = recent_rsi[price_max_idx]

        # Look for earlier high
        earlier_prices = recent_prices[:-5]  # Exclude last 5 days
        if not earlier_prices:
            return None

        earlier_price_max_idx = earlier_prices.index(max(earlier_prices))
        earlier_rsi_at_high = recent_rsi[earlier_price_max_idx]

        # Check for bearish divergence
        price_high = max(recent_prices)
        earlier_price_high = max(earlier_prices)

        if (price_high > earlier_price_high and
            rsi_at_price_high < earlier_rsi_at_high and
            earlier_rsi_at_high - rsi_at_price_high >= threshold):

            return {
                'price_high': price_high,
                'rsi_low': rsi_at_price_high,
                'strength': earlier_rsi_at_high - rsi_at_price_high
            }

        return None

    def _confirm_signal(self, prices: List[float], confirmation_period: int, bullish: bool) -> bool:
        """Confirm signal with price action."""
        if len(prices) < confirmation_period + 1:
            return False

        recent_prices = prices[-confirmation_period:]

        if bullish:
            # For bullish signal, look for price starting to recover
            return recent_prices[-1] > recent_prices[0]
        else:
            # For bearish signal, look for price starting to decline
            return recent_prices[-1] < recent_prices[0]

    def _calculate_confidence(self, divergence_strength: float, threshold: float) -> float:
        """Calculate signal confidence based on divergence strength."""
        base_confidence = 0.5
        strength_ratio = divergence_strength / threshold

        # Higher confidence for stronger divergences
        confidence_boost = min(strength_ratio - 1, 0.4)

        return min(base_confidence + confidence_boost, 1.0)</content>
</xai:function_call</xai:function_call
name="create_file">
<parameter name="path">/Users/stephenlopez/Projects/Trading Projects/nexus/new_project/simple_rsi_divergence_validation.py
