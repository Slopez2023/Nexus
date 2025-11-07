"""
Simplified Backtesting Engine - Fixes complex multi-index issues
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from ..strategies import BaseStrategy, TradeSignal
from .models import BacktestConfig, BacktestResult, PortfolioState, Trade

logger = logging.getLogger(__name__)


class SimpleBacktestEngine:
    """Simplified backtesting engine avoiding complex multi-index issues."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        # Risk controls
        self.daily_loss_limit = 0.02  # Stop trading if >2% daily loss
        self.kill_switch = False  # Emergency halt
        self.portfolio_exposure_limit = 0.10  # Max 10% total exposure

    def activate_kill_switch(self):
        """Activate emergency kill switch to halt all trading."""
        self.kill_switch = True
        logger.warning("Kill switch activated - all trading halted")

    def deactivate_kill_switch(self):
        """Deactivate kill switch to resume trading."""
        self.kill_switch = False
        logger.info("Kill switch deactivated - trading resumed")

    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self.kill_switch

    def run_backtest(self, strategy: BaseStrategy, market_data: pd.DataFrame) -> BacktestResult:
        """Run simplified backtest."""
        logger.info("Starting simplified backtest")

        # Validate inputs
        self._validate_inputs(strategy, market_data)

        # Prepare data
        data = self._prepare_data(market_data)

        # Initialize portfolio
        portfolio = {
            'cash': self.config.initial_capital,
            'positions': {},
            'total_value': self.config.initial_capital
        }

        portfolio_history = []
        trades = []

        # Simple daily loop
        for date in data.index:
            daily_data = data.loc[date]

            # Check kill switch
            if self.kill_switch:
                logger.warning(f"Kill switch activated - skipping trading on {date}")
                continue

            # Check daily loss limit
            if len(portfolio_history) > 0:
                prev_portfolio = portfolio_history[-1]
                daily_return = (portfolio['total_value'] - prev_portfolio.total_value) / prev_portfolio.total_value
                if daily_return < -self.daily_loss_limit:
                    logger.warning(f"Daily loss limit exceeded ({daily_return:.1%}) - halting trading")
                    self.kill_switch = True  # Activate kill switch
                    continue

            # Create market data dict for strategy
            market_dict = {
                'price': daily_data['close'],
                'volume': daily_data['volume'],
                'returns': daily_data.get('returns', 0)
            }

            # Generate signals
            signals = strategy.generate_signals(SimpleMarketDataAdapter(market_dict))

            # Execute signals (with risk controls)
            for signal in signals:
                # Get position size from signal metadata (risk control)
                position_size = signal.metadata.get('position_size', 0.02)  # Default 2%

                # Check portfolio exposure limit
                current_exposure = abs(portfolio['positions'].get('stock', 0) * daily_data['close']) / portfolio['total_value']
                max_additional_exposure = self.portfolio_exposure_limit - current_exposure

                if max_additional_exposure <= 0:
                    logger.debug(f"Portfolio exposure limit reached ({current_exposure:.1%}) - skipping trade")
                    continue

                # Limit position size to available exposure
                effective_position_size = min(position_size, max_additional_exposure)
                quantity = int((portfolio['total_value'] * effective_position_size) / daily_data['close'])

                if signal.direction == 'long':
                    if quantity > 0:
                        # Buy
                        cost = quantity * daily_data['close']
                        if portfolio['cash'] >= cost:
                            portfolio['cash'] -= cost
                            portfolio['positions']['stock'] = portfolio['positions'].get('stock', 0) + quantity
                            trades.append(Trade(
                                timestamp=date,
                                symbol='STOCK',
                                side='buy',
                                quantity=quantity,
                                price=daily_data['close'],
                                commission=0,
                                slippage=0,
                                total_cost=cost
                            ))
                else:  # short
                    # Sell existing position
                    current_pos = portfolio['positions'].get('stock', 0)
                    if current_pos > 0:
                        sell_quantity = min(quantity, current_pos)
                        proceeds = sell_quantity * daily_data['close']
                        portfolio['cash'] += proceeds
                        portfolio['positions']['stock'] -= sell_quantity
                        trades.append(Trade(
                            timestamp=date,
                            symbol='STOCK',
                            side='sell',
                            quantity=sell_quantity,
                            price=daily_data['close'],
                            commission=0,
                            slippage=0,
                            total_cost=0
                        ))

            # Update portfolio value
            position_value = portfolio['positions'].get('stock', 0) * daily_data['close']
            portfolio['total_value'] = portfolio['cash'] + position_value

            # Record state
            portfolio_history.append(PortfolioState(
                timestamp=date,
                cash=portfolio['cash'],
                positions={'stock': position_value},
                total_value=portfolio['total_value']
            ))

        # Calculate results
        equity_curve = pd.Series([p.total_value for p in portfolio_history],
                               index=[p.timestamp for p in portfolio_history])

        result = BacktestResult(
            config=self.config,
            portfolio_states=portfolio_history,
            trades=trades,
            performance=self._calculate_performance(equity_curve),
            significance_tests=[],  # Simplified
            equity_curve=equity_curve,
            drawdowns=self._calculate_drawdowns(equity_curve),
            monthly_returns=self._calculate_monthly_returns(equity_curve),
            risk_metrics=self._calculate_risk_metrics(equity_curve, trades),
            execution_time=0,
            data_quality_score=1.0,
            warnings=[]
        )

        logger.info("Simplified backtest completed")
        return result

    def _validate_inputs(self, strategy, data):
        """Basic validation."""
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Missing columns: {required_cols}")

    def _prepare_data(self, data):
        """Prepare data with date index."""
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def _calculate_performance(self, equity_curve):
        """Calculate basic performance metrics."""
        from .models import PerformanceMetrics

        returns = equity_curve.pct_change().dropna()
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annualized_return = returns.mean() * 252
        volatility = returns.std() * np.sqrt(252)
        sharpe = annualized_return / volatility if volatility > 0 else 0

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sharpe,  # Simplified
            max_drawdown=0,  # Will be calculated separately
            win_rate=(returns > 0).mean(),
            profit_factor=1.0,  # Simplified
            total_trades=0,
            avg_trade_pnl=0,
            best_trade=0,
            worst_trade=0
        )

    def _calculate_drawdowns(self, equity_curve):
        """Calculate drawdowns."""
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        return drawdowns

    def _calculate_monthly_returns(self, equity_curve):
        """Calculate monthly returns."""
        return equity_curve.resample('M').last().pct_change().dropna()

    def _calculate_risk_metrics(self, equity_curve, trades):
        """Calculate risk metrics."""
        returns = equity_curve.pct_change().dropna()
        var_95 = returns.quantile(0.05)
        max_dd = abs(self._calculate_drawdowns(equity_curve).min())

        return {
            'value_at_risk_95': var_95,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'winning_trades': sum(1 for t in trades if t.net_amount > 0),
            'avg_trade_pnl': sum(t.net_amount for t in trades) / len(trades) if trades else 0
        }


class SimpleMarketDataAdapter:
    """Simple market data adapter for strategies."""

    def __init__(self, data_dict):
        self.data = data_dict

    def get_price(self, symbol):
        return self.data.get('price', 100)

    def get_volume(self, symbol):
        return self.data.get('volume', 1000)

    def get_historical_data(self, symbol, days):
        # Return dummy historical data
        return [{'close': self.data.get('price', 100)} for _ in range(min(days, 30))]
