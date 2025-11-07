"""Portfolio simulation engine.

Handles position management, trade execution, and P&L calculations
with realistic portfolio mechanics.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

from .models import (
    PortfolioState, Position, Trade, TradeCost, TradeSide,
    RiskLimits, BacktestConfig
)
from .costs import TransactionCostModel, MarketDataProtocol

logger = logging.getLogger(__name__)


class PortfolioSimulator:
    """Realistic portfolio simulation with position tracking.

    Manages cash, positions, and executes trades with proper accounting.
    Includes risk limits and position validation.
    """

    def __init__(self, config: BacktestConfig):
        """Initialize portfolio simulator.

        Args:
            config: Backtest configuration
        """
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_history: List[PortfolioState] = []

        # Risk management
        self.risk_limits = config.risk_limits
        self.daily_loss_limit = config.initial_capital * self.risk_limits.max_daily_loss_pct
        self.max_drawdown_limit = config.initial_capital * self.risk_limits.max_drawdown_pct

        # Performance tracking
        self.peak_value = config.initial_capital
        self.current_drawdown = 0.0

        logger.info(f"Initialized portfolio: ${config.initial_capital:,.2f} capital")

    def execute_trade(self, symbol: str, quantity: int, price: float,
                     timestamp: datetime, cost_model: TransactionCostModel,
                     market_data: MarketDataProtocol) -> Optional[Trade]:
        """Execute a trade with cost calculations and risk checks.

        Args:
            symbol: Trading symbol
            quantity: Positive for buy, negative for sell
            price: Execution price
            timestamp: Trade timestamp
            cost_model: Cost calculation model
            market_data: Market data interface

        Returns:
            Trade: Executed trade record, or None if rejected
        """
        # Determine trade side
        side = TradeSide.BUY if quantity > 0 else TradeSide.SELL

        # Risk checks
        if not self._check_risk_limits(symbol, quantity, price):
            logger.warning(f"Trade rejected by risk limits: {symbol} {quantity}@{price}")
            return None

        # Calculate costs
        cost_breakdown = cost_model.calculate_trade_cost(
            symbol, quantity, price, side, market_data
        )

        # Execute the trade
        trade = self._process_trade(symbol, quantity, price, timestamp, cost_breakdown)

        # Update positions
        self._update_positions(trade)

        # Record trade
        self.trades.append(trade)

        logger.info(f"Executed {side.value}: {symbol} {abs(quantity)}@{price:.2f} "
                   f"cost=${cost_breakdown.total:.2f}")

        return trade

    def _check_risk_limits(self, symbol: str, quantity: int, price: float) -> bool:
        """Check if trade violates risk limits.

        Args:
            symbol: Trading symbol
            quantity: Trade quantity
            price: Trade price

        Returns:
            True if trade is allowed
        """
        notional_value = abs(quantity) * price
        current_value = self.get_portfolio_value()

        # Position size limit
        position_limit = current_value * self.risk_limits.max_position_size_pct
        if notional_value > position_limit:
            return False

        # Check existing position size after trade
        existing_qty = self.positions.get(symbol, Position(symbol, 0, 0.0)).quantity
        new_qty = existing_qty + quantity
        new_position_value = abs(new_qty) * price

        if new_position_value > position_limit:
            return False

        # Daily loss limit (simplified - would need daily tracking)
        # Max drawdown limit
        if self.current_drawdown > self.max_drawdown_limit:
            return False

        return True

    def _process_trade(self, symbol: str, quantity: int, price: float,
                      timestamp: datetime, costs: TradeCost) -> Trade:
        """Process trade execution and accounting.

        Args:
            symbol: Trading symbol
            quantity: Trade quantity
            price: Execution price
            timestamp: Trade timestamp
            costs: Trade cost breakdown

        Returns:
            Trade: Completed trade record
        """
        side = TradeSide.BUY if quantity > 0 else TradeSide.SELL

        # Create trade record
        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=costs.commission,
            slippage=costs.slippage + costs.market_impact,  # Combine for simplicity
            total_cost=costs.total
        )

        # Update cash
        cash_flow = trade.net_amount
        self.cash -= cash_flow

        return trade

    def _update_positions(self, trade: Trade) -> None:
        """Update position records after trade execution.

        Args:
            trade: Executed trade
        """
        symbol = trade.symbol

        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol, 0, 0.0)

        position = self.positions[symbol]
        old_quantity = position.quantity
        old_avg_price = position.average_price

        # Calculate new position
        if trade.side == TradeSide.BUY:
            # Buy: increase position
            total_cost = (old_quantity * old_avg_price) + (trade.quantity * trade.price)
            new_quantity = old_quantity + trade.quantity
            new_avg_price = total_cost / new_quantity if new_quantity != 0 else 0.0
        else:
            # Sell: decrease position (no average price change for sells)
            new_quantity = old_quantity + trade.quantity  # quantity is negative
            new_avg_price = old_avg_price

        # Update position
        position.quantity = new_quantity
        position.average_price = new_avg_price

        # Remove position if flat
        if new_quantity == 0:
            del self.positions[symbol]

    def update_market_prices(self, prices: Dict[str, float], timestamp: datetime) -> None:
        """Update all positions with current market prices.

        Args:
            prices: Current prices for all symbols
            timestamp: Update timestamp
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_market_price(prices[symbol])

        # Create portfolio state snapshot
        portfolio_state = PortfolioState(
            timestamp=timestamp,
            cash=self.cash,
            positions=self.positions.copy()
        )

        self.portfolio_history.append(portfolio_state)

        # Update drawdown tracking
        if portfolio_state.total_value > self.peak_value:
            self.peak_value = portfolio_state.total_value
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.peak_value - portfolio_state.total_value) / self.peak_value

    def get_portfolio_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Get current total portfolio value.

        Args:
            current_prices: Optional current prices override

        Returns:
            Total portfolio value
        """
        position_value = 0.0

        for symbol, position in self.positions.items():
            if current_prices and symbol in current_prices:
                price = current_prices[symbol]
            else:
                # Use last known market value
                price = position.market_value / position.quantity if position.quantity != 0 else 0.0

            position_value += position.quantity * price

        return self.cash + position_value

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Position if exists, None otherwise
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all current positions."""
        return self.positions.copy()

    def get_portfolio_history(self) -> List[PortfolioState]:
        """Get complete portfolio history."""
        return self.portfolio_history.copy()

    def get_trades(self) -> List[Trade]:
        """Get all executed trades."""
        return self.trades.copy()

    def get_current_portfolio_state(self) -> PortfolioState:
        """Get current portfolio state."""
        if self.portfolio_history:
            return self.portfolio_history[-1]
        else:
            # Return initial state
            return PortfolioState(
                timestamp=self.config.start_date,
                cash=self.cash,
                positions=self.positions.copy()
            )

    def calculate_daily_pnl(self) -> float:
        """Calculate daily P&L."""
        if len(self.portfolio_history) < 2:
            return 0.0

        current = self.portfolio_history[-1].total_value
        previous = self.portfolio_history[-2].total_value

        return current - previous

    def is_risk_limits_breached(self) -> bool:
        """Check if any risk limits are breached.

        Returns:
            True if any risk limit is breached
        """
        # Drawdown check
        if self.current_drawdown > self.max_drawdown_limit:
            return True

        # Position concentration check
        total_value = self.get_portfolio_value()
        for position in self.positions.values():
            position_pct = abs(position.market_value) / total_value
            if position_pct > self.risk_limits.max_position_size_pct:
                return True

        return False

    def get_portfolio_summary(self) -> Dict[str, any]:
        """Get portfolio summary statistics."""
        total_value = self.get_portfolio_value()
        position_value = sum(abs(pos.market_value) for pos in self.positions.values())

        return {
            "total_value": total_value,
            "cash": self.cash,
            "position_value": position_value,
            "num_positions": len(self.positions),
            "peak_value": self.peak_value,
            "current_drawdown": self.current_drawdown,
            "total_trades": len(self.trades),
            "risk_limits_breached": self.is_risk_limits_breached()
        }

    def reset(self) -> None:
        """Reset portfolio to initial state (for testing)."""
        self.cash = self.config.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.portfolio_history.clear()
        self.peak_value = self.config.initial_capital
        self.current_drawdown = 0.0

        logger.info("Portfolio reset to initial state")
