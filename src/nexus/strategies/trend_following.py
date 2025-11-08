"""Trend-following trading strategy implementation.

This module implements trend-following strategies based on moving average crossovers.
Trend-following works well in trending markets and has been extensively studied.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class TrendFollowingStrategy(BaseStrategy):
    """Trend-following strategy using moving average crossovers.

    Based on extensive academic research: moving average crossovers capture
    trending markets effectively (Brock et al. 1992, "Simple Technical Trading Rules
    and the Stochastic Properties of Stock Returns").
    """

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        confirmation_period: int = 5,
        max_positions: Optional[int] = None,
        min_price: float = 1.0,
        min_volume: int = 1000,
    ) -> None:
        """Initialize trend-following strategy.

        Args:
            fast_period: Fast moving average period
            slow_period: Slow moving average period
            confirmation_period: Days to wait for confirmation
            max_positions: Maximum positions per side
            min_price: Minimum stock price filter
            min_volume: Minimum daily volume filter
        """
        super().__init__(
            fast_period=fast_period,
            slow_period=slow_period,
            confirmation_period=confirmation_period,
            max_positions=max_positions,
            min_price=min_price,
            min_volume=min_volume,
        )

    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        params = self.get_parameters()

        # MA periods
        if not isinstance(params['fast_period'], int) or params['fast_period'] < 5:
            raise ParameterError("fast_period must be integer >= 5")

        if not isinstance(params['slow_period'], int) or params['slow_period'] <= params['fast_period']:
            raise ParameterError("slow_period must be integer > fast_period")

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
            name="Trend-Following Strategy",
            description="Captures trends using moving average crossovers",
            version="1.0.0",
            parameters={
                'fast_period': ParameterSpec(
                    name='fast_period',
                    type='int',
                    default=50,
                    min_value=5,
                    max_value=100,
                    description="Fast moving average period"
                ),
                'slow_period': ParameterSpec(
                    name='slow_period',
                    type='int',
                    default=200,
                    min_value=20,
                    max_value=300,
                    description="Slow moving average period"
                ),
                'confirmation_period': ParameterSpec(
                    name='confirmation_period',
                    type='int',
                    default=5,
                    min_value=1,
                    max_value=20,
                    description="Days to wait for crossover confirmation"
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
                'strategy_type': 'trend_following',
                'horizon': 'medium-term',
                'volatility': 'medium',
                'market_regime_sensitivity': 'excels in trending markets, struggles in sideways',
                'crash_risk': 'high (trend reversals hurt)',
            },
            tags=['trend_following', 'technical', 'moving_averages', 'crossover', 'quantitative'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 7),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate trend-following signals based on MA crossovers.

        Uses dual moving average crossover: fast MA crosses above slow MA = bullish,
        fast MA crosses below slow MA = bearish.

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals

        Raises:
            SignalError: If signal generation fails
        """
        try:
            params = self.get_parameters()
            fast_period = params['fast_period']
            slow_period = params['slow_period']
            confirmation = params['confirmation_period']

            # Get historical data
            historical_data = market_data.get_historical_data('SPY', slow_period + confirmation + 10)

            if len(historical_data) < slow_period + confirmation:
                return []

            # Extract prices
            prices = [entry['close'] for entry in historical_data]
            prices = [p for p in prices if isinstance(p, (int, float)) and p > 0]

            if len(prices) < slow_period + confirmation:
                return []

            # Calculate moving averages
            fast_ma = self._calculate_sma(prices, fast_period)
            slow_ma = self._calculate_sma(prices, slow_period)

            # Detect crossovers
            bullish_crossover = self._detect_bullish_crossover(fast_ma, slow_ma, confirmation)
            bearish_crossover = self._detect_bearish_crossover(fast_ma, slow_ma, confirmation)

            signals = []
            timestamp = datetime.utcnow()

            if bullish_crossover:
                confidence = min(bullish_crossover['strength'] / 0.02, 1.0)  # Strength based on MA separation
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='long',
                    confidence=confidence,
                    reasoning=f"Trend Following: Fast MA({fast_period}) crossed above Slow MA({slow_period})",
                    metadata={
                        'strategy': 'trend_following',
                        'crossover_type': 'bullish',
                        'fast_period': fast_period,
                        'slow_period': slow_period,
                        'crossover_strength': bullish_crossover['strength'],
                        'position_size': 0.02,
                        'max_portfolio_exposure': 0.10
                    }
                )
                signals.append(signal)

            elif bearish_crossover:
                confidence = min(bearish_crossover['strength'] / 0.02, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='short',
                    confidence=confidence,
                    reasoning=f"Trend Following: Fast MA({fast_period}) crossed below Slow MA({slow_period})",
                    metadata={
                        'strategy': 'trend_following',
                        'crossover_type': 'bearish',
                        'fast_period': fast_period,
                        'slow_period': slow_period,
                        'crossover_strength': bearish_crossover['strength'],
                        'position_size': 0.02,
                        'max_portfolio_exposure': 0.10
                    }
                )
                signals.append(signal)

            return signals

        except Exception as e:
            self._logger.error(f"Trend-following signal generation failed: {e}")
            raise SignalError(f"Failed to generate trend-following signals: {e}") from e

    def _calculate_sma(self, prices: List[float], period: int) -> List[float]:
        """Calculate simple moving average."""
        sma = []
        for i in range(len(prices)):
            if i < period - 1:
                sma.append(None)  # Not enough data
            else:
                avg = sum(prices[i-period+1:i+1]) / period
                sma.append(avg)
        return sma

    def _detect_bullish_crossover(self, fast_ma: List[float], slow_ma: List[float],
                                 confirmation: int) -> Optional[Dict[str, Any]]:
        """Detect bullish crossover (fast MA crosses above slow MA)."""
        if len(fast_ma) < confirmation + 1 or len(slow_ma) < confirmation + 1:
            return None

        # Check recent crossover
        for i in range(confirmation, len(fast_ma)):
            prev_fast = fast_ma[i-confirmation]
            prev_slow = slow_ma[i-confirmation]
            curr_fast = fast_ma[i]
            curr_slow = slow_ma[i]

            if (prev_fast is None or prev_slow is None or
                curr_fast is None or curr_slow is None):
                continue

            # Bullish crossover: fast was below slow, now above
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                strength = abs(curr_fast - curr_slow) / curr_slow  # Relative strength
                return {'strength': strength}

        return None

    def _detect_bearish_crossover(self, fast_ma: List[float], slow_ma: List[float],
                                 confirmation: int) -> Optional[Dict[str, Any]]:
        """Detect bearish crossover (fast MA crosses below slow MA)."""
        if len(fast_ma) < confirmation + 1 or len(slow_ma) < confirmation + 1:
            return None

        # Check recent crossover
        for i in range(confirmation, len(fast_ma)):
            prev_fast = fast_ma[i-confirmation]
            prev_slow = slow_ma[i-confirmation]
            curr_fast = fast_ma[i]
            curr_slow = slow_ma[i]

            if (prev_fast is None or prev_slow is None or
                curr_fast is None or curr_slow is None):
                continue

            # Bearish crossover: fast was above slow, now below
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                strength = abs(curr_fast - curr_slow) / curr_slow  # Relative strength
                return {'strength': strength}

        return None

    def _calculate_confidence(self, crossover_strength: float) -> float:
        """Calculate signal confidence based on crossover strength."""
        base_confidence = 0.6
        strength_bonus = min(crossover_strength * 10, 0.3)  # Max 0.3 bonus

        return min(base_confidence + strength_bonus, 1.0)</content>
</xai:function_call</xai:function_call
name="create_file">
<parameter name="path">/Users/stephenlopez/Projects/Trading Projects/nexus/new_project/simple_trend_following_validation.py
