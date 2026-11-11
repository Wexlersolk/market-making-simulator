"""Network and Latency Models for High-Frequency Market Making.

Why Latency Matters in Market Making:
1. Feed Latency: Delay between an event occurring on the exchange and the MM receiving the market data tick.
2. Order Routing Latency: Delay between MM generating an order/cancel and the matching engine receiving it.
3. In-Flight Orders: Orders sent by the MM are not yet active in the book during transit.
4. Cancel Races: If market conditions change and the MM attempts to cancel a stale quote,
   an aggressive taker order can hit the resting quote at the exchange before the cancel packet arrives.
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class LatencyProfile:
    """Configurable latency profile with base delays and network jitter."""
    feed_latency_ms: float = 1.0     # Exchange -> Trader market data delay (ms)
    order_latency_ms: float = 1.0    # Trader -> Exchange order submission delay (ms)
    jitter_std_ms: float = 0.1       # Gaussian jitter std deviation (ms)

    def sample_feed_latency_sec(self) -> float:
        """Sample feed transit time in seconds."""
        delay = self.feed_latency_ms + random.gauss(0, self.jitter_std_ms)
        return max(0.00001, delay / 1000.0)

    def sample_order_latency_sec(self) -> float:
        """Sample order routing transit time in seconds."""
        delay = self.order_latency_ms + random.gauss(0, self.jitter_std_ms)
        return max(0.00001, delay / 1000.0)


class InFlightRegistry:
    """Tracks orders currently in transit across the network."""

    def __init__(self):
        # order_id -> submission_timestamp
        self._in_flight_orders: dict[str, float] = {}
        # order_id -> cancel_request_timestamp
        self._in_flight_cancels: dict[str, float] = {}

    def record_submit(self, order_id: str, timestamp: float):
        self._in_flight_orders[order_id] = timestamp

    def confirm_arrival(self, order_id: str) -> Optional[float]:
        return self._in_flight_orders.pop(order_id, None)

    def record_cancel_request(self, order_id: str, timestamp: float):
        self._in_flight_cancels[order_id] = timestamp

    def confirm_cancel_arrival(self, order_id: str) -> Optional[float]:
        return self._in_flight_cancels.pop(order_id, None)

    def is_in_flight(self, order_id: str) -> bool:
        return order_id in self._in_flight_orders or order_id in self._in_flight_cancels
