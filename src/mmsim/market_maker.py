"""Market Maker Agent with inventory management and PnL attribution."""

from dataclasses import dataclass, field
from typing import Optional

from mmsim.strategy import AvellanedaStoikov
from mmsim.types import Order, OrderType, Side, Trade


@dataclass
class MarketMaker:
    """Simulated market maker tracking cash, inventory, and quoting decisions."""

    trader_id: str = "MM_AGENT"
    cash: float = 0.0
    inventory: float = 0.0
    max_inventory: float = 20.0
    model: AvellanedaStoikov = field(default_factory=AvellanedaStoikov)
    
    # Performance tracking
    spread_pnl: float = 0.0
    trades_count: int = 0
    active_bid_id: Optional[str] = None
    active_ask_id: Optional[str] = None

    def compute_quotes(
        self, mid_price: float, t: float = 0.0
    ) -> tuple[float, float, float]:
        """Generate optimal (bid, ask, reservation_price) given current inventory."""
        return self.model.optimal_quotes(mid_price, self.inventory, t)

    def on_fill(self, trade: Trade, current_mid: float):
        """Update inventory and spread PnL when our resting limit order fills."""
        self.trades_count += 1
        qty = trade.quantity
        px = trade.price

        if trade.maker_side == Side.BUY:
            # We bought at our bid price
            self.inventory += qty
            self.cash -= px * qty
            # Spread capture relative to mid at execution time
            self.spread_pnl += (current_mid - px) * qty
        else:
            # We sold at our ask price
            self.inventory -= qty
            self.cash += px * qty
            # Spread capture relative to mid at execution time
            self.spread_pnl += (px - current_mid) * qty

    def mark_to_market_pnl(self, current_mid: float) -> float:
        """Total PnL = Cash + Inventory marked to current mid-price."""
        return self.cash + (self.inventory * current_mid)

    def inventory_risk_ratio(self) -> float:
        """Normalized inventory risk between -1.0 (max short) and +1.0 (max long)."""
        if self.max_inventory <= 0:
            return 0.0
        return max(min(self.inventory / self.max_inventory, 1.0), -1.0)
