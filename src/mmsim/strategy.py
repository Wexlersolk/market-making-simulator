"""Market Making Strategies: Protocol, Fixed Spread Baseline, and Avellaneda-Stoikov.

Why Strategy Comparison Teaches Microstructure:
1. FixedSpreadStrategy: Quotes symmetric spread around mid without accounting for inventory.
   Result: In trending or toxic markets, inventory drifts to extremes and incurs massive drawdowns.
2. AvellanedaStoikovStrategy: Dynamically skews quotes based on current inventory q and volatility sigma.
   Result: Stabilizes inventory around zero by pricing aggressively to offload accumulated risk.
"""

from __future__ import annotations
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from mmsim.orderbook import OrderBook


class BaseStrategy(ABC):
    """Abstract interface for automated market making strategies."""

    @abstractmethod
    def generate_quotes(
        self, book: OrderBook, inventory: float, current_time: float
    ) -> tuple[Optional[float], Optional[float]]:
        """Return (target_bid_price, target_ask_price) given current book and inventory."""
        pass

    def should_requote(
        self,
        current_bid: Optional[float],
        current_ask: Optional[float],
        target_bid: Optional[float],
        target_ask: Optional[float],
        min_move_ticks: float = 1.0,
        tick_size: float = 0.01,
    ) -> bool:
        """Avoid spamming cancels/replaces if target price move is below threshold."""
        if (current_bid is None) != (target_bid is None):
            return True
        if (current_ask is None) != (target_ask is None):
            return True

        threshold = min_move_ticks * tick_size - 1e-9
        if current_bid is not None and target_bid is not None:
            if abs(current_bid - target_bid) >= threshold:
                return True
        if current_ask is not None and target_ask is not None:
            if abs(current_ask - target_ask) >= threshold:
                return True
        return False


@dataclass
class FixedSpreadStrategy(BaseStrategy):
    """Simple baseline strategy quoting fixed spread around mid price."""
    spread_ticks: int = 4
    tick_size: float = 0.01

    def generate_quotes(
        self, book: OrderBook, inventory: float, current_time: float
    ) -> tuple[Optional[float], Optional[float]]:
        mid = book.mid_price()
        if mid is None:
            return None, None
        half = (self.spread_ticks / 2.0) * self.tick_size
        bid = round(mid - half, 8)
        ask = round(mid + half, 8)
        return bid, ask


@dataclass
class AvellanedaStoikov(BaseStrategy):
    """Avellaneda-Stoikov (2008) High-Frequency Optimal Quoting Strategy.

    Formulation:
      r(s, q, t) = s - q * gamma * sigma^2 * (T - t)
      half_spread = (1 / gamma) * ln(1 + gamma / kappa)
      target_bid = r - half_spread
      target_ask = r + half_spread
    """
    gamma: float = 0.1         # Risk aversion parameter (gamma > 0)
    sigma: float = 0.25        # Volatility per unit time
    T: float = 1.0             # Trading session horizon (seconds or normalized)
    kappa: float = 1.5         # Order flow intensity decay
    tick_size: float = 0.01

    def reservation_price(self, mid_price: float, inventory: float, t: float = 0.0) -> float:
        """Reservation price penalizing inventory risk: r = s - q * gamma * sigma^2 * tau."""
        tau = max(0.001, self.T - t)
        return mid_price - (inventory * self.gamma * (self.sigma ** 2) * tau)

    def half_spread(self) -> float:
        """Optimal spread around reservation price."""
        if self.gamma <= 0 or self.kappa <= 0:
            return self.tick_size
        return (1.0 / self.gamma) * math.log(1.0 + (self.gamma / self.kappa))

    def optimal_quotes(
        self, mid_price: float, inventory: float, t: float = 0.0
    ) -> tuple[float, float, float]:
        """Compute (bid_price, ask_price, reservation_price)."""
        r = self.reservation_price(mid_price, inventory, t)
        hs = self.half_spread()
        bid = round(round((r - hs) / self.tick_size) * self.tick_size, 8)
        ask = round(round((r + hs) / self.tick_size) * self.tick_size, 8)
        if bid >= ask:
            ask = round(bid + self.tick_size, 8)
        return bid, ask, round(r, 8)

    def generate_quotes(
        self, book: OrderBook, inventory: float, current_time: float
    ) -> tuple[Optional[float], Optional[float]]:
        mid = book.mid_price()
        if mid is None:
            return None, None
        bid, ask, _ = self.optimal_quotes(mid, inventory, current_time)
        return bid, ask
