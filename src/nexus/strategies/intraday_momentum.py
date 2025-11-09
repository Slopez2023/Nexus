"""Intraday Momentum Strategy for NEXUS Framework.

This strategy integrates with NEXUS by inheriting from BaseStrategy and implementing
the required interface. It provides comprehensive validation, metadata, and signal generation.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from .base import BaseStrategy, TradeSignal, ParameterSpec, StrategyMetadata, MarketData, ParameterError, SignalError


class IntradayMomentumStrategy(BaseStrategy):
    """
    Intraday momentum strategy that works on 5-15 minute timeframes.

    Integrates with NEXUS framework by:
    - Inheriting from BaseStrategy
    - Implementing required abstract methods
    - Providing comprehensive parameter validation
    - Generating standardized TradeSignal objects
    - Including detailed metadata for management
    """

    def __init__(
        self,
        timeframe_minutes: int = 5,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        momentum_period: int = 10,
        volume_multiplier: float = 1.5,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.04,
        max_positions: int = 5,
        min_price_move: float = 0.005,
    ):
        """Initialize strategy with validated parameters."""
        super().__init__(
            timeframe_minutes=timeframe_minutes,
            rsi_period=rsi_period,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
            momentum_period=momentum_period,
            volume_multiplier=volume_multiplier,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_positions=max_positions,
            min_price_move=min_price_move,
        )

    def validate_parameters(self) -> bool:
        """Validate strategy parameters (required by NEXUS)."""
        params = self.get_parameters()

        # Timeframe validation
        if not isinstance(params['timeframe_minutes'], int) or params['timeframe_minutes'] not in [5, 15]:
            raise ParameterError("timeframe_minutes must be 5 or 15")

        # RSI validation
        if not isinstance(params['rsi_period'], int) or params['rsi_period'] < 2:
            raise ParameterError("rsi_period must be integer >= 2")

        if not (0 < params['rsi_oversold'] < params['rsi_overbought'] < 100):
            raise ParameterError("RSI thresholds must satisfy: 0 < rsi_oversold < rsi_overbought < 100")

        # Risk management validation
        for param in ['stop_loss_pct', 'take_profit_pct', 'min_price_move']:
            if not isinstance(params[param], (int, float)) or params[param] <= 0:
                raise ParameterError(f"{param} must be positive number")

        # Position limits
        if not isinstance(params['max_positions'], int) or params['max_positions'] < 1:
            raise ParameterError("max_positions must be integer >= 1")

        return True

    @property
    def metadata(self) -> StrategyMetadata:
        """Strategy metadata for NEXUS management and discovery."""
        return StrategyMetadata(
            name="Intraday Momentum Strategy",
            description="Short-term momentum strategy for 5-15 minute charts across multiple assets",
            version="1.0.0",
            parameters={
                'timeframe_minutes': ParameterSpec(
                    name='timeframe_minutes',
                    type='int',
                    default=5,
                    min_value=5,
                    max_value=15,
                    description="Chart timeframe in minutes"
                ),
                'rsi_period': ParameterSpec(
                    name='rsi_period',
                    type='int',
                    default=14,
                    min_value=2,
                    max_value=50,
                    description="RSI calculation period"
                ),
                'rsi_overbought': ParameterSpec(
                    name='rsi_overbought',
                    type='float',
                    default=70.0,
                    min_value=50.0,
                    max_value=90.0,
                    description="RSI level for overbought signals"
                ),
                'rsi_oversold': ParameterSpec(
                    name='rsi_oversold',
                    type='float',
                    default=30.0,
                    min_value=10.0,
                    max_value=50.0,
                    description="RSI level for oversold signals"
                ),
                'momentum_period': ParameterSpec(
                    name='momentum_period',
                    type='int',
                    default=10,
                    min_value=5,
                    max_value=20,
                    description="Period for momentum calculation"
                ),
                'volume_multiplier': ParameterSpec(
                    name='volume_multiplier',
                    type='float',
                    default=1.5,
                    min_value=1.0,
                    max_value=3.0,
                    description="Volume must be X times average"
                ),
                'stop_loss_pct': ParameterSpec(
                    name='stop_loss_pct',
                    type='float',
                    default=0.02,
                    min_value=0.005,
                    max_value=0.05,
                    description="Stop loss percentage"
                ),
                'take_profit_pct': ParameterSpec(
                    name='take_profit_pct',
                    type='float',
                    default=0.04,
                    min_value=0.01,
                    max_value=0.10,
                    description="Take profit percentage"
                ),
                'max_positions': ParameterSpec(
                    name='max_positions',
                    type='int',
                    default=5,
                    min_value=1,
                    max_value=20,
                    description="Maximum concurrent positions"
                ),
                'min_price_move': ParameterSpec(
                    name='min_price_move',
                    type='float',
                    default=0.005,
                    min_value=0.001,
                    max_value=0.02,
                    description="Minimum price move for entry"
                ),
            },
            risk_profile={
                'strategy_type': 'intraday_momentum',
                'horizon': 'very_short_term',
                'volatility': 'high',
                'market_regime_sensitivity': 'works well in trending intraday markets',
                'crash_risk': 'moderate (tight stops)',
            },
            tags=['intraday', 'momentum', 'technical', 'rsi', 'multi_asset'],
            author="NEXUS System",
            created_date=datetime(2024, 11, 9),
        )

    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """
        Generate trading signals (required by NEXUS).

        This method is called by NEXUS framework during live trading or backtesting.
        It uses the MarketData protocol to access price/volume data without knowing
        the specific implementation (could be live feed, historical database, etc.)
        """
        try:
            params = self.get_parameters()
            timeframe = params['timeframe_minutes']

            # Get universe from NEXUS (framework provides this)
            universe = self._get_universe(market_data)
            if not universe:
                return []

            signals = []
            timestamp = datetime.utcnow()

            # Generate signals for each asset in universe
            for symbol in universe:
                try:
                    # Get intraday data (NEXUS provides this interface)
                    intraday_data = market_data.get_intraday_data(
                        symbol, timeframe, periods=100
                    )

                    if len(intraday_data) < params['rsi_period'] + params['momentum_period']:
                        continue

                    # Apply strategy logic
                    asset_signals = self._generate_asset_signals(
                        symbol, intraday_data, timestamp
                    )
                    signals.extend(asset_signals)

                except Exception as e:
                    self._logger.warning(f"Failed to generate signals for {symbol}: {e}")
                    continue

            return signals

        except Exception as e:
            self._logger.error(f"Signal generation failed: {e}")
            raise SignalError(f"Failed to generate intraday momentum signals: {e}") from e

    def _get_universe(self, market_data: MarketData) -> List[str]:
        """Get trading universe from NEXUS framework."""
        # In real implementation, NEXUS would provide filtered universe
        # based on liquidity, volatility, etc.
        if hasattr(market_data, 'get_intraday_universe'):
            return market_data.get_intraday_universe()
        else:
            # Fallback for development - would be configured in production
            return ['AAPL', 'GOOGL', 'MSFT', 'TSLA']  # Sample liquid stocks

    def _generate_asset_signals(self, symbol: str, data: List[Dict[str, Any]], timestamp: datetime) -> List[TradeSignal]:
        """Generate signals for a single asset."""
        params = self.get_parameters()

        # Convert to format expected by strategy logic
        df_data = self._convert_to_dataframe(data)

        # Apply technical analysis
        df_data = self._add_indicators(df_data)

        # Check for signals
        current = df_data.iloc[-1]

        signals = []

        # Long signal conditions
        if (current['rsi'] < params['rsi_oversold'] and
            current['momentum'] > params['min_price_move'] and
            current['volume_ratio'] > params['volume_multiplier']):

            confidence = self._calculate_confidence(current, 'long', params)

            signal = TradeSignal(
                symbol=symbol,
                timestamp=timestamp,
                direction='long',
                confidence=confidence,
                reasoning=f"Intraday momentum long: RSI {current['rsi']:.1f}, momentum {current['momentum']:.1%}",
                metadata={
                    'strategy': 'intraday_momentum',
                    'timeframe': params['timeframe_minutes'],
                    'indicators': {
                        'rsi': current['rsi'],
                        'momentum': current['momentum'],
                        'volume_ratio': current['volume_ratio']
                    },
                    'risk_management': {
                        'stop_loss_pct': params['stop_loss_pct'],
                        'take_profit_pct': params['take_profit_pct']
                    }
                }
            )
            signals.append(signal)

        # Short signal conditions
        elif (current['rsi'] > params['rsi_overbought'] and
              current['momentum'] < -params['min_price_move'] and
              current['volume_ratio'] > params['volume_multiplier']):

            confidence = self._calculate_confidence(current, 'short', params)

            signal = TradeSignal(
                symbol=symbol,
                timestamp=timestamp,
                direction='short',
                confidence=confidence,
                reasoning=f"Intraday momentum short: RSI {current['rsi']:.1f}, momentum {current['momentum']:.1%}",
                metadata={
                    'strategy': 'intraday_momentum',
                    'timeframe': params['timeframe_minutes'],
                    'indicators': {
                        'rsi': current['rsi'],
                        'momentum': current['momentum'],
                        'volume_ratio': current['volume_ratio']
                    },
                    'risk_management': {
                        'stop_loss_pct': params['stop_loss_pct'],
                        'take_profit_pct': params['take_profit_pct']
                    }
                }
            )
            signals.append(signal)

        return signals

    def _convert_to_dataframe(self, data: List[Dict[str, Any]]) -> 'pd.DataFrame':
        """Convert raw data to DataFrame format."""
        import pandas as pd

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise SignalError(f"Missing required column: {col}")

        return df

    def _add_indicators(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """Add technical indicators to DataFrame."""
        params = self.get_parameters()

        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], params['rsi_period'])

        # Momentum
        df['momentum'] = df['close'].pct_change(params['momentum_period'])

        # Volume ratio
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        return df

    def _calculate_rsi(self, prices: 'pd.Series', period: int) -> 'pd.Series':
        """Calculate RSI indicator."""
        import pandas as pd
        import numpy as np

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_confidence(self, current: 'pd.Series', direction: str, params: Dict[str, Any]) -> float:
        """Calculate signal confidence score."""
        base_confidence = 0.5

        # RSI extremity boost
        rsi = current['rsi']
        if direction == 'long':
            rsi_boost = min((params['rsi_oversold'] - rsi) / params['rsi_oversold'], 0.2)
        else:
            rsi_boost = min((rsi - params['rsi_overbought']) / (100 - params['rsi_overbought']), 0.2)

        # Momentum strength boost
        momentum = abs(current['momentum'])
        momentum_boost = min(momentum / params['min_price_move'], 0.2)

        # Volume confirmation boost
        volume_boost = min((current['volume_ratio'] - 1) * 0.1, 0.1)

        confidence = base_confidence + rsi_boost + momentum_boost + volume_boost
        return min(confidence, 1.0)
