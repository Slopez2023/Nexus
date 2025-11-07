"""Transaction cost modeling for realistic backtesting.

Implements comprehensive cost calculations including commissions,
slippage, market impact, and exchange fees.
"""

from typing import Dict, Any, Protocol
import logging

from .models import CostConfig, TradeCost, TradeSide

logger = logging.getLogger(__name__)


class MarketDataProtocol(Protocol):
    """Protocol for market data access."""

    def get_price(self, symbol: str) -> float: ...
    def get_spread(self, symbol: str) -> float: ...
    def get_volume(self, symbol: str) -> int: ...


class TransactionCostModel:
    """Professional transaction cost modeling.

    Calculates realistic trading costs including:
    - Commissions (per share, minimum, maximum)
    - Slippage (price impact from spread)
    - Market impact (large order price movement)
    - Exchange fees

    All costs are calculated based on real market mechanics.
    """

    def __init__(self, config: CostConfig):
        """Initialize cost model with configuration.

        Args:
            config: Cost configuration parameters
        """
        self.config = config
        self._validate_config()

        logger.info(f"Initialized cost model: commission={config.commission_per_share}, "
                   f"slippage={config.slippage_bps}bps")

    def _validate_config(self) -> None:
        """Validate cost configuration."""
        if self.config.commission_per_share < 0:
            raise ValueError("Commission per share must be non-negative")

        if self.config.commission_minimum < 0:
            raise ValueError("Commission minimum must be non-negative")

        if self.config.slippage_bps < 0:
            raise ValueError("Slippage must be non-negative")

        if self.config.market_impact_bps < 0:
            raise ValueError("Market impact must be non-negative")

        if self.config.exchange_fees < 0:
            raise ValueError("Exchange fees must be non-negative")

    def calculate_trade_cost(self, symbol: str, quantity: int, price: float,
                           side: TradeSide, market_data: MarketDataProtocol) -> TradeCost:
        """Calculate total cost for executing a trade.

        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Execution price
            side: Buy or sell
            market_data: Market data interface

        Returns:
            TradeCost: Breakdown of all costs
        """
        notional_value = abs(quantity) * price

        # Commission costs
        commission = self._calculate_commission(notional_value, quantity)

        # Slippage costs (based on spread)
        slippage = self._calculate_slippage(symbol, quantity, price, side, market_data)

        # Market impact (for large orders)
        market_impact = self._calculate_market_impact(symbol, quantity, price, market_data)

        # Exchange fees
        exchange_fees = notional_value * self.config.exchange_fees

        total_cost = commission + slippage + market_impact + exchange_fees

        cost_breakdown = TradeCost(
            commission=commission,
            slippage=slippage,
            market_impact=market_impact,
            exchange_fees=exchange_fees,
            total=total_cost
        )

        logger.debug(f"Trade cost for {symbol} {side.value} {quantity}@{price:.2f}: "
                    f"commission={commission:.2f}, slippage={slippage:.2f}, "
                    f"impact={market_impact:.2f}, fees={exchange_fees:.2f}, "
                    f"total={total_cost:.2f}")

        return cost_breakdown

    def _calculate_commission(self, notional_value: float, quantity: int) -> float:
        """Calculate commission costs.

        Uses per-share commission with minimum and maximum bounds.
        """
        per_share_cost = abs(quantity) * self.config.commission_per_share
        commission = max(per_share_cost, self.config.commission_minimum)

        if self.config.commission_maximum is not None:
            commission = min(commission, self.config.commission_maximum)

        return commission

    def _calculate_slippage(self, symbol: str, quantity: int, price: float,
                          side: TradeSide, market_data: MarketDataProtocol) -> float:
        """Calculate slippage costs.

        Slippage occurs when the execution price differs from the quoted price
        due to market movement during order execution.
        """
        # Get current spread
        spread = market_data.get_spread(symbol)
        if spread <= 0:
            spread = price * 0.001  # Assume 0.1% spread if not available

        # Slippage is typically half the spread for market orders
        # Adjust based on order size (larger orders have more slippage)
        base_slippage = spread * 0.5

        # Size adjustment - larger orders relative to volume have more slippage
        volume = market_data.get_volume(symbol)
        if volume > 0:
            size_ratio = abs(quantity) / volume
            size_multiplier = min(size_ratio * 10, 2.0)  # Max 2x slippage
        else:
            size_multiplier = 1.0

        slippage_amount = base_slippage * size_multiplier

        # Convert to cost (positive for both buy and sell)
        return slippage_amount

    def _calculate_market_impact(self, symbol: str, quantity: int, price: float,
                               market_data: MarketDataProtocol) -> float:
        """Calculate market impact costs.

        Market impact occurs when large orders move the market price.
        Based on square-root model of price impact.
        """
        notional_value = abs(quantity) * price
        volume = market_data.get_volume(symbol)

        if volume <= 0:
            return 0.0

        # Participation rate (percentage of daily volume)
        participation_rate = abs(quantity) / volume

        # Square-root impact model: Impact ∝ √(participation_rate)
        # This is a simplified version of real market impact models
        impact_bps = self.config.market_impact_bps * (participation_rate ** 0.5)

        # Convert basis points to dollar amount
        impact_cost = notional_value * (impact_bps / 10000)

        return impact_cost

    def estimate_round_trip_costs(self, symbol: str, quantity: int, price: float,
                                market_data: MarketDataProtocol) -> Dict[str, float]:
        """Estimate costs for a round-trip trade (buy + sell).

        Args:
            symbol: Trading symbol
            quantity: Number of shares
            price: Current price
            market_data: Market data interface

        Returns:
            Dictionary with cost breakdown for round trip
        """
        # Buy costs
        buy_costs = self.calculate_trade_cost(symbol, quantity, price, TradeSide.BUY, market_data)

        # Sell costs (assume same price for estimation)
        sell_costs = self.calculate_trade_cost(symbol, -quantity, price, TradeSide.SELL, market_data)

        total_commission = buy_costs.commission + sell_costs.commission
        total_slippage = buy_costs.slippage + sell_costs.slippage
        total_impact = buy_costs.market_impact + sell_costs.market_impact
        total_fees = buy_costs.exchange_fees + sell_costs.exchange_fees
        total_cost = buy_costs.total + sell_costs.total

        # Calculate as percentage of notional value
        notional_value = quantity * price
        cost_pct = (total_cost / notional_value) * 100

        return {
            "total_cost": total_cost,
            "cost_percentage": cost_pct,
            "commission": total_commission,
            "slippage": total_slippage,
            "market_impact": total_impact,
            "exchange_fees": total_fees,
            "effective_spread_bps": (total_slippage / notional_value) * 10000
        }

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost model configuration summary."""
        return {
            "commission_per_share": self.config.commission_per_share,
            "commission_minimum": self.config.commission_minimum,
            "commission_maximum": self.config.commission_maximum,
            "slippage_bps": self.config.slippage_bps,
            "market_impact_bps": self.config.market_impact_bps,
            "exchange_fees_pct": self.config.exchange_fees * 100
        }


# Factory functions for common cost models
def create_realistic_cost_model() -> TransactionCostModel:
    """Create cost model with realistic retail trading costs."""
    config = CostConfig(
        commission_per_share=0.005,  # $0.005 per share
        commission_minimum=1.0,      # $1 minimum
        slippage_bps=5.0,            # 5 bps slippage
        market_impact_bps=2.0,       # 2 bps market impact
        exchange_fees=0.0001         # 0.01% exchange fees
    )
    return TransactionCostModel(config)


def create_institutional_cost_model() -> TransactionCostModel:
    """Create cost model with institutional trading costs."""
    config = CostConfig(
        commission_per_share=0.001,  # $0.001 per share
        commission_minimum=0.5,      # $0.50 minimum
        slippage_bps=2.0,            # 2 bps slippage
        market_impact_bps=1.0,       # 1 bps market impact
        exchange_fees=0.00005        # 0.005% exchange fees
    )
    return TransactionCostModel(config)


def create_zero_cost_model() -> TransactionCostModel:
    """Create cost model with zero costs (for theoretical analysis)."""
    config = CostConfig(
        commission_per_share=0.0,
        commission_minimum=0.0,
        slippage_bps=0.0,
        market_impact_bps=0.0,
        exchange_fees=0.0
    )
    return TransactionCostModel(config)
