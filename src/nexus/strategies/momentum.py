"""Momentum trading strategy implementation.

This module implements the momentum strategy based on Jegadeesh-Titman (1993).
Buys stocks with strong recent performance, sells short poor performers.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class MomentumStrategy(BaseStrategy):
    """Momentum strategy based on past 3-month returns with RSI filter.

    Enhanced Jegadeesh-Titman methodology for individual stocks:
    - Rank stocks by cumulative returns over 3-month formation period
    - Buy top 20% performers with RSI < 75 (not overbought)
    - Sell/short bottom 20% performers with RSI > 25 (not oversold)
    - Hold for 1 month (short-term momentum)
    - Includes position sizing and risk controls
    - Optimized for individual stock momentum, not index ETFs
    """

    def __init__(
        self,
        formation_period_months: int = 3,
        holding_period_months: int = 1,
        percentile: float = 20.0,
        max_positions: Optional[int] = 10,
        min_price: float = 10.0,
        min_volume: int = 100000,
        rsi_period: int = 14,
        rsi_overbought: float = 75.0,
        rsi_oversold: float = 25.0,
    ) -> None:
        """Initialize momentum strategy.

        Args:
            formation_period_months: Months to look back for ranking (default: 3)
            holding_period_months: Months to hold positions (default: 1)
            percentile: Percentage of stocks to buy/sell (default: 20.0)
            max_positions: Maximum positions per side (default: 10)
            min_price: Minimum stock price filter
            min_volume: Minimum daily volume filter
            rsi_period: Period for RSI calculation (default: 14)
            rsi_overbought: RSI threshold for overbought (default: 70.0)
            rsi_oversold: RSI threshold for oversold (default: 30.0)
        """
        super().__init__(
            formation_period_months=formation_period_months,
            holding_period_months=holding_period_months,
            percentile=percentile,
            max_positions=max_positions,
            min_price=min_price,
            min_volume=min_volume,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
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

        # RSI parameters
        if not isinstance(params['rsi_period'], int) or params['rsi_period'] < 2:
            raise ParameterError("rsi_period must be integer >= 2")

        if not isinstance(params['rsi_overbought'], (int, float)) or not (50 < params['rsi_overbought'] < 100):
            raise ParameterError("rsi_overbought must be between 50 and 100")

        if not isinstance(params['rsi_oversold'], (int, float)) or not (0 < params['rsi_oversold'] < 50):
            raise ParameterError("rsi_oversold must be between 0 and 50")

        if params['rsi_overbought'] <= params['rsi_oversold']:
            raise ParameterError("rsi_overbought must be greater than rsi_oversold")

        return True

    @property
    def metadata(self) -> StrategyMetadata:
        """Strategy metadata."""
        return StrategyMetadata(
            name="Momentum Strategy",
            description="Buys past winners with RSI < 75, sells past losers with RSI > 25 based on 3-month returns",
            version="2.0.0",
            parameters={
                'formation_period_months': ParameterSpec(
                    name='formation_period_months',
                    type='int',
                    default=3,
                    min_value=1,
                    max_value=12,
                    description="Months to look back for ranking stocks"
                ),
                'holding_period_months': ParameterSpec(
                    name='holding_period_months',
                    type='int',
                    default=1,
                    min_value=1,
                    max_value=12,
                    description="Months to hold positions"
                ),
                'percentile': ParameterSpec(
                    name='percentile',
                    type='float',
                    default=20.0,
                    min_value=0.1,
                    max_value=50.0,
                    description="Percentage of stocks to buy/sell"
                ),
                'max_positions': ParameterSpec(
                    name='max_positions',
                    type='int',
                    default=10,
                    min_value=1,
                    description="Maximum positions per side"
                ),
                'min_price': ParameterSpec(
                    name='min_price',
                    type='float',
                    default=5.0,
                    min_value=0.0,
                    description="Minimum stock price filter"
                ),
                'min_volume': ParameterSpec(
                    name='min_volume',
                    type='int',
                    default=50000,
                    min_value=0,
                    description="Minimum daily volume filter"
                ),
                'rsi_period': ParameterSpec(
                    name='rsi_period',
                    type='int',
                    default=14,
                    min_value=2,
                    max_value=50,
                    description="Period for RSI calculation"
                ),
                'rsi_overbought': ParameterSpec(
                    name='rsi_overbought',
                    type='float',
                    default=75.0,
                    min_value=50.0,
                    max_value=100.0,
                    description="RSI threshold for overbought (long filter)"
                ),
                'rsi_oversold': ParameterSpec(
                    name='rsi_oversold',
                    type='float',
                    default=25.0,
                    min_value=0.0,
                    max_value=50.0,
                    description="RSI threshold for oversold (short filter)"
                ),
            },
            risk_profile={
                'strategy_type': 'momentum',
                'horizon': 'short-term',
                'volatility': 'high',
                'market_regime_sensitivity': 'works in bull markets, risky in bear markets',
                'crash_risk': 'high in bear markets',
            },
            tags=['momentum', 'technical', 'quantitative', 'rsi-filtered'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 7),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate momentum signals with RSI filter across stock universe.

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
            rsi_lookback = max(formation_days, params['rsi_period'] * 2)  # Need enough data for RSI

            # Get trading universe
            universe = self._get_universe(market_data)
            if not universe:
                return []

            signals = []
            timestamp = datetime.utcnow()

            # Calculate momentum and RSI for each stock
            stock_data = []
            for symbol in universe:
                try:
                    # Get price and volume data
                    current_price = market_data.get_price(symbol)
                    current_volume = market_data.get_volume(symbol)

                    # Apply filters
                    if current_price < params['min_price'] or current_volume < params['min_volume']:
                        continue

                    # Get historical data for momentum and RSI
                    hist_data = market_data.get_historical_data(symbol, rsi_lookback + 10)
                    if len(hist_data) < rsi_lookback:
                        continue

                    # Calculate momentum (formation period return)
                    momentum_return = self._calculate_cumulative_return(hist_data, formation_days)
                    if momentum_return is None:
                        continue

                    # Calculate RSI
                    rsi_value = self._calculate_rsi(hist_data, params['rsi_period'])
                    if rsi_value is None:
                        continue

                    stock_data.append({
                        'symbol': symbol,
                        'momentum': momentum_return,
                        'rsi': rsi_value,
                        'price': current_price,
                        'volume': current_volume
                    })

                except Exception:
                    continue  # Skip problematic stocks

            if len(stock_data) < 10:  # Need minimum universe size
                return []

            # Sort by momentum
            stock_data.sort(key=lambda x: x['momentum'], reverse=True)

            # Calculate percentile thresholds
            num_positions = min(params['max_positions'], int(len(stock_data) * params['percentile'] / 100))

            # Generate long signals (top performers with RSI < overbought and positive momentum)
            long_candidates = [s for s in stock_data[:num_positions]
                             if s['rsi'] < params['rsi_overbought'] and s['momentum'] > 0.03]  # 3%+ return
            for stock in long_candidates[:params['max_positions']]:
                position_size = self._calculate_position_size(stock['price'])
                confidence = self._calculate_confidence(stock['momentum'], params['percentile'], True)

                signal = TradeSignal(
                        symbol=stock['symbol'],
                        timestamp=timestamp,
                        direction='long',
                        confidence=confidence,
                        reasoning=f"Momentum long: {stock['momentum']:.1%} return, RSI={stock['rsi']:.1f}",
                        metadata={
                            'strategy': 'momentum_rsi',
                            'momentum_return': stock['momentum'],
                            'rsi': stock['rsi'],
                            'formation_period': params['formation_period_months'],
                            'position_size': position_size,
                            'max_portfolio_exposure': 0.05  # Max 5% per position
                        }
                    )
                signals.append(signal)

                # Generate short signals (bottom performers with RSI > oversold and negative momentum)
                short_candidates = [s for s in stock_data[-num_positions:]
                if s['rsi'] > params['rsi_oversold'] and s['momentum'] < -0.03]  # -3%+ decline
                for stock in short_candidates[:params['max_positions']]:
                    position_size = self._calculate_position_size(stock['price'])
                    confidence = self._calculate_confidence(stock['momentum'], params['percentile'], False)

                    signal = TradeSignal(
                        symbol=stock['symbol'],
                        timestamp=timestamp,
                        direction='short',
                        confidence=confidence,
                        reasoning=f"Momentum short: {stock['momentum']:.1%} return, RSI={stock['rsi']:.1f}",
                        metadata={
                            'strategy': 'momentum_rsi',
                            'momentum_return': stock['momentum'],
                            'rsi': stock['rsi'],
                            'formation_period': params['formation_period_months'],
                            'position_size': position_size,
                            'max_portfolio_exposure': 0.05  # Max 5% per position
                        }
                    )
                    signals.append(signal)

                return signals

        except Exception as e:
            self._logger.error(f"Momentum signal generation failed: {e}")
            raise SignalError(f"Failed to generate momentum signals: {e}") from e

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

    def _calculate_cumulative_return(self, hist_data: List[Dict[str, Any]], days: int) -> Optional[float]:
        """Calculate cumulative return over period from historical data.

        Args:
            hist_data: Historical price data (list of dicts with 'close' key)
            days: Number of days to look back

        Returns:
            Cumulative return or None if insufficient data
        """
        try:
            if len(hist_data) < days:
                return None

            # Use the most recent 'days' worth of data
            # Assume hist_data is ordered with most recent last
            relevant_data = hist_data[-days:] if len(hist_data) >= days else hist_data

            closes = [entry['close'] for entry in relevant_data if 'close' in entry and isinstance(entry['close'], (int, float)) and entry['close'] > 0]

            if len(closes) < 2:
                return None

            start_price = closes[0]
            end_price = closes[-1]

            return (end_price - start_price) / start_price

        except Exception:
            return None

    def _calculate_rsi(self, hist_data: List[Dict[str, Any]], period: int) -> Optional[float]:
        """Calculate RSI for the most recent period.

        Args:
            hist_data: Historical price data (list of dicts with 'close' key)
            period: RSI calculation period

        Returns:
            RSI value (0-100) or None if insufficient data
        """
        if len(hist_data) < period + 1:
            return None

        # Extract closing prices (most recent first)
        closes = [entry['close'] for entry in hist_data[-period-1:] if 'close' in entry]
        if len(closes) < period + 1:
            return None

        # Calculate price changes
        changes = []
        for i in range(1, len(closes)):
            changes.append(closes[i] - closes[i-1])

        # Calculate gains and losses
        gains = [max(change, 0) for change in changes]
        losses = [max(-change, 0) for change in changes]

        if len(gains) < period:
            return None

        # Calculate average gain and loss
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on price (risk management).

        Args:
            price: Current stock price

        Returns:
            Position size as fraction of portfolio (0.01 = 1%)
        """
        # Simple position sizing: lower price = larger position (up to 3%)
        # Higher price = smaller position (minimum 0.5%)
        if price < 10:
            return 0.03  # 3% for cheap stocks
        elif price < 50:
            return 0.02  # 2% for mid-range
        elif price < 200:
            return 0.015  # 1.5% for expensive stocks
        else:
            return 0.01  # 1% for very expensive stocks

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
