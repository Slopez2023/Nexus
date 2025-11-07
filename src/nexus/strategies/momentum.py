"""Momentum trading strategy implementation.

This module implements the momentum strategy based on Jegadeesh-Titman (1993).
Buys stocks with strong recent performance, sells short poor performers.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class MomentumStrategy(BaseStrategy):
    """Momentum strategy based on past 6-month returns.

    Follows Jegadeesh-Titman methodology:
    - Rank stocks by cumulative returns over formation period
    - Buy top performers, short bottom performers
    - Hold for specified period
    """

    def __init__(
        self,
        formation_period_months: int = 6,
        holding_period_months: int = 6,
        percentile: float = 10.0,
        max_positions: Optional[int] = None,
        min_price: float = 1.0,
        min_volume: int = 1000,
    ) -> None:
        """Initialize momentum strategy.

        Args:
            formation_period_months: Months to look back for ranking (default: 6)
            holding_period_months: Months to hold positions (default: 6)
            percentile: Percentage of stocks to buy/sell (default: 10.0)
            max_positions: Maximum positions per side (None = unlimited)
            min_price: Minimum stock price filter
            min_volume: Minimum daily volume filter
        """
        super().__init__(
            formation_period_months=formation_period_months,
            holding_period_months=holding_period_months,
            percentile=percentile,
            max_positions=max_positions,
            min_price=min_price,
            min_volume=min_volume,
        )

    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        params = self.get_parameters()

        # Formation period
        if not isinstance(params['formation_period_months'], int) or params['formation_period_months'] < 1:
            raise ParameterError("formation_period_months must be positive integer")

        # Holding period
        if not isinstance(params['holding_period_months'], int) or params['holding_period_months'] < 1:
            raise ParameterError("holding_period_months must be positive integer")

        # Percentile
        if not isinstance(params['percentile'], (int, float)) or not (0 < params['percentile'] <= 50):
            raise ParameterError("percentile must be between 0 and 50")

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
            name="Momentum Strategy",
            description="Buys past winners, sells past losers based on 6-month returns",
            version="1.0.0",
            parameters={
                'formation_period_months': ParameterSpec(
                    name='formation_period_months',
                    type='int',
                    default=6,
                    min_value=1,
                    max_value=12,
                    description="Months to look back for ranking stocks"
                ),
                'holding_period_months': ParameterSpec(
                    name='holding_period_months',
                    type='int',
                    default=6,
                    min_value=1,
                    max_value=12,
                    description="Months to hold positions"
                ),
                'percentile': ParameterSpec(
                    name='percentile',
                    type='float',
                    default=10.0,
                    min_value=0.1,
                    max_value=50.0,
                    description="Percentage of stocks to buy/sell"
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
                'strategy_type': 'momentum',
                'horizon': 'medium-term',
                'volatility': 'high',
                'market_regime_sensitivity': 'trending markets preferred',
                'crash_risk': 'high in bear markets',
            },
            tags=['momentum', 'technical', 'quantitative'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 7),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate true Jegadeesh-Titman momentum signals.

        Simplified implementation: Buy when market shows strong upward momentum,
        sell/short when it shows strong downward momentum.

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals

        Raises:
            SignalError: If signal generation fails
        """
        try:
            params = self.get_parameters()
            formation_days = params['formation_period_months'] * 21  # ~21 trading days per month

            # Get historical data
            historical_data = market_data.get_historical_data('SPY', formation_days + 5)

            if len(historical_data) < formation_days:
                return []

            # Calculate formation period return
            start_price = historical_data[0]['close']
            end_price = historical_data[formation_days - 1]['close']

            if start_price <= 0:
                return []

            formation_return = (end_price - start_price) / start_price

            signals = []
            timestamp = datetime.utcnow()

            # JT Momentum: Strong trends continue
            if formation_return > 0.05:  # 5%+ up = buy
                confidence = min(formation_return * 5, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='long',
                    confidence=confidence,
                    reasoning=f"JT Momentum: +{formation_return:.1%} over {params['formation_period_months']} months",
                    metadata={
                        'strategy': 'jt_momentum',
                        'formation_return': formation_return,
                        'formation_period': params['formation_period_months'],
                        'position_size': 0.02,  # Risk control: Max 2% per trade
                        'max_portfolio_exposure': 0.10  # Risk control: Max 10% total exposure
                    }
                )
                signals.append(signal)

            elif formation_return < -0.05:  # 5%+ down = short
                confidence = min(abs(formation_return) * 5, 1.0)
                signal = TradeSignal(
                    symbol='SPY',
                    timestamp=timestamp,
                    direction='short',
                    confidence=confidence,
                    reasoning=f"JT Momentum: {formation_return:.1%} over {params['formation_period_months']} months",
                    metadata={
                        'strategy': 'jt_momentum',
                        'formation_return': formation_return,
                        'formation_period': params['formation_period_months'],
                        'position_size': 0.02,  # Risk control: Max 2% per trade
                        'max_portfolio_exposure': 0.10  # Risk control: Max 10% total exposure
                    }
                )
                signals.append(signal)

            return signals

        except Exception as e:
            self._logger.error(f"JT momentum signal generation failed: {e}")
            raise SignalError(f"Failed to generate JT momentum signals: {e}") from e

    def _get_universe(self, market_data: MarketData) -> List[str]:
        """Get trading universe from market data.

        Note: This method assumes market_data has a get_universe() method.
        In real implementation, this would be defined in the MarketData protocol.
        """
        # Placeholder - in real system, market_data would provide this
        if hasattr(market_data, 'get_universe'):
            return market_data.get_universe()
        else:
            # Fallback for testing - would need to be configured
            raise SignalError("Market data must provide universe")

    def _calculate_cumulative_return(self, market_data: MarketData, symbol: str, days: int) -> Optional[float]:
        """Calculate cumulative return over period.

        Args:
            market_data: Market data interface
            symbol: Stock symbol
            days: Number of days to look back

        Returns:
            Cumulative return or None if insufficient data
        """
        try:
            data = market_data.get_historical_data(symbol, days + 10)  # Extra days for safety

            if len(data) < 2:
                return None

            # Sort by date (assuming data is list of dicts with 'close' key)
            data.sort(key=lambda x: x.get('date', ''))

            start_price = None
            end_price = None

            for entry in data:
                if 'close' not in entry:
                    continue
                price = entry['close']
                if not isinstance(price, (int, float)) or price <= 0:
                    continue

                if start_price is None:
                    start_price = price
                end_price = price

            if start_price is None or end_price is None:
                return None

            return (end_price - start_price) / start_price

        except Exception:
            return None

    def _calculate_confidence(self, return_val: float, percentile: float, is_winner: bool) -> float:
        """Calculate signal confidence based on return magnitude.

        Args:
            return_val: Stock's cumulative return
            percentile: Strategy percentile threshold
            is_winner: True for long signals, False for short

        Returns:
            Confidence score between 0.5 and 1.0
        """
        # Base confidence on return magnitude
        # Stronger returns = higher confidence
        base_confidence = 0.5

        if is_winner:
            # For winners, confidence increases with return strength
            if return_val > 0.5:  # 50%+ return
                confidence_boost = 0.4
            elif return_val > 0.2:  # 20%+ return
                confidence_boost = 0.3
            elif return_val > 0.1:  # 10%+ return
                confidence_boost = 0.2
            elif return_val > 0.05:  # 5%+ return
                confidence_boost = 0.1
            else:
                confidence_boost = 0.0
        else:
            # For losers, confidence increases with negative return strength
            if return_val < -0.5:  # -50%+ decline
                confidence_boost = 0.4
            elif return_val < -0.2:  # -20%+ decline
                confidence_boost = 0.3
            elif return_val < -0.1:  # -10%+ decline
                confidence_boost = 0.2
            elif return_val < -0.05:  # -5%+ decline
                confidence_boost = 0.1
            else:
                confidence_boost = 0.0

        return min(base_confidence + confidence_boost, 1.0)
