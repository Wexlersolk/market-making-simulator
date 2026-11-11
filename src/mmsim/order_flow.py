"""Stochastic Order Flow Generator (Poisson Arrivals & Microstructure Dynamics).

Why Poisson Processes for Market Flow?
1. In microstructure theory (Glosten-Milgrom, Kyle, Avellaneda-Stoikov), order arrivals are modeled
   as point processes with intensity lambda.
2. Inter-arrival time Delta t follows the Exponential distribution:
   Delta t = -ln(U) / lambda, where U ~ Uniform(0, 1).
3. Types of Flow:
   - Retail Noise: Uninformed, random direction, provides passive spread capture for MM.
   - Informed Flow: Correlated with future price drift, causing adverse selection.
   - Background Limit Orders: Provides surrounding book depth so the MM isn't the sole participant.
"""

from __future__ import annotations
import math
import random
import uuid
from dataclasses import dataclass
from typing import Optional

from mmsim.types import Order, OrderType, Side


@dataclass
class FlowConfig:
    market_order_rate: float = 5.0     # Average market orders per second (lambda)
    limit_order_rate: float = 10.0     # Average background limit orders per second
    cancel_rate: float = 8.0           # Average cancellations per second
    mean_order_size: float = 5.0       # Mean order size (exponential/lognormal)


class PoissonOrderFlow:
    """Generates stochastic order flow according to Poisson arrival processes."""

    def __init__(self, config: Optional[FlowConfig] = None):
        self.config = config or FlowConfig()
        self._order_counter = 0

    def sample_interarrival_time(self, rate: float) -> float:
        """Sample time until next event from Exponential(rate)."""
        if rate <= 0:
            return float("inf")
        u = max(1e-12, random.random())
        return -math.log(u) / rate

    def sample_order_quantity(self) -> float:
        """Sample discrete order size."""
        # Mean size with minimum 1 unit
        size = 1.0 + random.expovariate(1.0 / max(1.0, self.config.mean_order_size - 1.0))
        return round(size, 0)

    def next_market_order(
        self, timestamp: float, buy_prob: float = 0.5, trader_id: str = "RetailTaker"
    ) -> tuple[float, Order]:
        """Generate next incoming market order with arrival timestamp."""
        delay = self.sample_interarrival_time(self.config.market_order_rate)
        arrival_time = round(timestamp + delay, 6)
        side = Side.BUY if random.random() < buy_prob else Side.SELL
        qty = self.sample_order_quantity()
        self._order_counter += 1

        order = Order(
            order_id=f"MKT_{self._order_counter}_{uuid.uuid4().hex[:4]}",
            trader_id=trader_id,
            side=side,
            price=0.0,
            quantity=qty,
            timestamp=arrival_time,
            order_type=OrderType.MARKET,
        )
        return arrival_time, order

    def next_limit_order(
        self,
        timestamp: float,
        mid_price: float,
        tick_size: float = 0.01,
        spread_ticks: int = 2,
        trader_id: str = "BackgroundLP",
    ) -> tuple[float, Order]:
        """Generate background resting limit order near top of book."""
        delay = self.sample_interarrival_time(self.config.limit_order_rate)
        arrival_time = round(timestamp + delay, 6)
        side = Side.BUY if random.random() < 0.5 else Side.SELL
        offset_ticks = random.randint(1, max(2, spread_ticks * 3))
        qty = self.sample_order_quantity()
        self._order_counter += 1

        if side == Side.BUY:
            price = round(mid_price - offset_ticks * tick_size, 8)
        else:
            price = round(mid_price + offset_ticks * tick_size, 8)

        price = max(tick_size, price)

        order = Order(
            order_id=f"LMT_{self._order_counter}_{uuid.uuid4().hex[:4]}",
            trader_id=trader_id,
            side=side,
            price=price,
            quantity=qty,
            timestamp=arrival_time,
            order_type=OrderType.LIMIT,
        )
        return arrival_time, order
