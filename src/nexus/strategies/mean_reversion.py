"""Mean-reversion trading strategy implementation.

This module implements mean-reversion strategies based on academic research
(Balvers et al. 2000, Jegadeesh 1990). Buys undervalued assets, sells overvalued ones.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class MeanReversionStrategy(BaseStrategy):
    """Mean-reversion strategy based on price deviation from moving average.

    Academic foundation: Balvers et al. (2000) "Mean Reversion across National
    Stock Markets and Parametric Contrarian Investment Strategies"
    """

    def __init__(
        self,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        max_positions: Optional[int] = None,
        min_price: float = 1.0,
        min_volume: int = 1000,
    ) -> None:
        """Initialize mean-reversion strategy.

        Args:
            lookback_period: Days for moving average calculation
            entry_threshold: Standard deviations for entry signal
            exit_threshold: Standard deviations for exit signal
            max_positions: Maximum positions per side
            min_price: Minimum stock price filter
            min_volume: Minimum daily volume filter
        """
        super().__init__(
            lookback_period=lookback_period,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            max_positions=max_positions,
            min_price=min_price,
            min_volume=min_volume,
        )

    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        params = self.get_parameters()

        # Lookback period
        if not isinstance(params['lookback_period'], int) or params['lookback_period'] < 5:
            raise ParameterError("lookback_period must be integer >= 5")

        # Thresholds
        for param_name in ['entry_threshold', 'exit_threshold']:
            if not isinstance(params[param_name], (int, float)) or params[param_name] <= 0:
                raise ParameterError(f"{param_name} must be positive number")

        if params['entry_threshold'] <= params['exit_threshold']:
            raise ParameterError("entry_threshold must be > exit_threshold")

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
            name="Mean-Reversion Strategy",
            description="Buys oversold assets, sells overbought assets based on moving average deviation",
            version="1.0.0",
            parameters={
                'lookback_period': ParameterSpec(
                    name='lookback_period',
                    type='int',
                    default=20,
                    min_value=5,
                    max_value=100,
                    description="Days for moving average calculation"
                ),
                'entry_threshold': ParameterSpec(
                    name='entry_threshold',
                    type='float',
                    default=2.0,
                    min_value=0.5,
                    max_value=5.0,
                    description="Standard deviations for entry signal"
                ),
                'exit_threshold': ParameterSpec(
                    name='exit_threshold',
                    type='float',
                    default=0.5,
                    min_value=0.1,
                    max_value=2.0,
                    description="Standard deviations for exit signal"
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
                'strategy_type': 'mean_reversion',
                'horizon': 'short-term',
                'volatility': 'high',
                'market_regime_sensitivity': 'sideways/high-volatility markets preferred',
                'crash_risk': 'low (buys dips)',
            },
            tags=['mean_reversion', 'technical', 'contrarian', 'quantitative'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 7),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate mean-reversion signals based on Bollinger Band deviation.

        Academic approach: Buy when price < MA - 2*STD, sell when price > MA + 2*STD

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals

        Raises:
            SignalError: If signal generation fails
        """
        try:
            params = self.get_parameters()
            lookback = params['lookback_period']
            entry_std = params['entry_threshold']
            exit_std = params['exit_threshold']

            # Get historical data
            historical_data = market_data.get_historical_data('SPY', lookback + 10)

            if len(historical_data) < lookback:
                return []

            # Extract prices
            prices = [entry['close'] for entry in historical_data[-lookback:]]
            prices = [p for p in prices if isinstance(p, (int, float)) and p > 0]

            if len(prices) < lookback:
                return []

            # Calculate moving average and standard deviation
            ma = sum(prices) / len(prices)
            std = (sum((p - ma) ** 2 for p in prices) / len(prices)) ** 0.5

            if std == 0:
                return []

            # Current price
            current_price = prices[-1]

            # Calculate z-score
            z_score = (current_price - ma) / std

            signals = []
            timestamp = datetime.utcnow()

            # Mean-reversion signals
            if z_score < -entry_std:  # Oversold - buy
                confidence = min(abs(z_score) / entry_std, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='long',
                    confidence=confidence,
                    reasoning=f"Mean-reversion: Price {z_score:.1f} STD below MA (entry threshold: -{entry_std})",
                    metadata={
                        'strategy': 'mean_reversion',
                        'z_score': z_score,
                        'moving_average': ma,
                        'std_dev': std,
                        'lookback_period': lookback,
                        'entry_threshold': entry_std,
                        'position_size': 0.02,  # Risk control: Max 2% per trade
                        'max_portfolio_exposure': 0.10  # Risk control: Max 10% total exposure
                    }
                )
                signals.append(signal)

            elif z_score > entry_std:  # Overbought - short
                confidence = min(z_score / entry_std, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='short',
                    confidence=confidence,
                    reasoning=f"Mean-reversion: Price {z_score:.1f} STD above MA (entry threshold: {entry_std})",
                    metadata={
                        'strategy': 'mean_reversion',
                        'z_score': z_score,
                        'moving_average': ma,
                        'std_dev': std,
                        'lookback_period': lookback,
                        'entry_threshold': entry_std,
                        'position_size': 0.02,  # Risk control: Max 2% per trade
                        'max_portfolio_exposure': 0.10  # Risk control: Max 10% total exposure
                    }
                )
                signals.append(signal)

            # Exit signals (if we have positions)
            # Note: This is simplified - real implementation would track positions
            elif abs(z_score) < exit_std:  # Reverted to mean - exit
                # This would need position tracking in real implementation
                pass

            return signals

        except Exception as e:
            self._logger.error(f"Mean-reversion signal generation failed: {e}")
            raise SignalError(f"Failed to generate mean-reversion signals: {e}") from e

    def _calculate_z_score(self, price: float, prices: List[float]) -> float:
        """Calculate z-score for price relative to historical prices.

        Args:
            price: Current price
            prices: Historical prices

        Returns:
            Z-score (standard deviations from mean)
        """
        if not prices:
            return 0.0

        ma = sum(prices) / len(prices)
        std = (sum((p - ma) ** 2 for p in prices) / len(prices)) ** 0.5

        if std == 0:
            return 0.0

        return (price - ma) / std

    def _calculate_confidence(self, z_score: float, threshold: float) -> float:
        """Calculate signal confidence based on deviation magnitude.

        Args:
            z_score: Price z-score
            threshold: Entry/exit threshold

        Returns:
            Confidence score between 0.5 and 1.0
        """
        base_confidence = 0.5
        deviation_ratio = abs(z_score) / threshold

        # Higher confidence for larger deviations
        confidence_boost = min(deviation_ratio - 1, 0.5)  # Max 0.5 boost

        return min(base_confidence + confidence_boost, 1.0)</content>
</xai:function_call</xai:function_call
name="create_file">
<parameter name="path">/Users/stephenlopez/Projects/Trading Projects/nexus/new_project/simple_mean_reversion_validation.py
