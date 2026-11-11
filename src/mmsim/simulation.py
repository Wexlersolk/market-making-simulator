"""Market Simulation Engine with Noise, Momentum, and Toxic Flow regimes."""

import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mmsim.market_maker import MarketMaker
from mmsim.orderbook import OrderBook
from mmsim.types import Order, OrderType, Side, Trade


class FlowRegime(Enum):
    NOISE = "Retail Noise (Spread Capture)"
    MOMENTUM = "Trending Momentum (Inventory Pressure)"
    TOXIC = "Informed / Toxic Shock (Adverse Selection)"


@dataclass
class SimEvent:
    timestamp: float
    event_type: str  # "TRADE", "QUOTE", "PRICE_MOVE", "SHOCK"
    description: str
    details: dict = field(default_factory=dict)


class MarketSimulator:
    """Simulates market environment with background liquidity, price dynamics, and taker flow."""

    def __init__(
        self,
        initial_price: float = 100.0,
        tick_size: float = 0.05,
        volatility: float = 0.15,
        flow_regime: FlowRegime = FlowRegime.NOISE,
    ):
        self.tick_size = tick_size
        self.fair_price = initial_price
        self.volatility = volatility
        self.flow_regime = flow_regime
        self.book = OrderBook(tick_size=tick_size)
        self.mm = MarketMaker(trader_id="MM_USER")
        self.step_count = 0
        self.current_time = 0.0
        self.recent_events: list[SimEvent] = []

        # Seed initial book
        self._seed_background_liquidity()

    def _round_price(self, price: float) -> float:
        return round(round(price / self.tick_size) * self.tick_size, 4)

    def _seed_background_liquidity(self):
        """Place realistic background limit orders around fair price."""
        for i in range(1, 10):
            bp = self._round_price(self.fair_price - i * self.tick_size * 2)
            ap = self._round_price(self.fair_price + i * self.tick_size * 2)
            b_qty = round(random.uniform(5, 25), 0)
            a_qty = round(random.uniform(5, 25), 0)

            self.book.add_limit_order(
                Order(f"BG_B_{i}_{uuid.uuid4().hex[:4]}", "OtherLP", Side.BUY, bp, b_qty, self.current_time)
            )
            self.book.add_limit_order(
                Order(f"BG_A_{i}_{uuid.uuid4().hex[:4]}", "OtherLP", Side.SELL, ap, a_qty, self.current_time)
            )

    def update_mm_quotes(self, bid_price: float, ask_price: float, quote_size: float = 5.0) -> list[SimEvent]:
        """Cancel old MM quotes and place new quotes."""
        events: list[SimEvent] = []

        # Cancel previous quotes
        if self.mm.active_bid_id:
            self.book.cancel_order(self.mm.active_bid_id)
            self.mm.active_bid_id = None
        if self.mm.active_ask_id:
            self.book.cancel_order(self.mm.active_ask_id)
            self.mm.active_ask_id = None

        bid_p = self._round_price(bid_price)
        ask_p = self._round_price(ask_price)

        if bid_p < ask_p:
            # Place new bid
            bid_id = f"MM_BID_{self.step_count}"
            bid_order = Order(
                order_id=bid_id,
                trader_id=self.mm.trader_id,
                side=Side.BUY,
                price=bid_p,
                quantity=quote_size,
                timestamp=self.current_time,
                is_mm=True,
            )
            t_bid = self.book.add_limit_order(bid_order)
            self.mm.active_bid_id = bid_id

            # Place new ask
            ask_id = f"MM_ASK_{self.step_count}"
            ask_order = Order(
                order_id=ask_id,
                trader_id=self.mm.trader_id,
                side=Side.SELL,
                price=ask_p,
                quantity=quote_size,
                timestamp=self.current_time,
                is_mm=True,
            )
            t_ask = self.book.add_limit_order(ask_order)
            self.mm.active_ask_id = ask_id

            # Check if any quotes matched immediately
            for trade in t_bid + t_ask:
                if trade.maker_trader_id == self.mm.trader_id:
                    self.mm.on_fill(trade, self.fair_price)
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=f"MM Quote instantly crossed! Filled {trade.quantity} @ ${trade.price:.2f}",
                    ))

        return events

    def step(self, auto_quote: bool = True) -> list[SimEvent]:
        """Advance simulation by 1 discrete tick."""
        self.step_count += 1
        self.current_time += 1.0
        events: list[SimEvent] = []

        # 1. Update Fair Price (Brownian motion + shocks)
        dt = 0.05
        drift = 0.0
        shock = 0.0

        if self.flow_regime == FlowRegime.MOMENTUM:
            drift = 0.04  # persistent upward/downward drift
        elif self.flow_regime == FlowRegime.TOXIC:
            # 15% probability of toxic whale jump
            if random.random() < 0.15:
                direction = random.choice([-1, 1])
                shock = direction * (self.tick_size * random.randint(4, 10))

        price_step = (drift * dt) + (self.volatility * (dt ** 0.5) * random.gauss(0, 1)) + shock
        self.fair_price = round(max(self.fair_price + price_step, self.tick_size * 5), 4)

        if abs(shock) > 0.001:
            events.append(SimEvent(
                timestamp=self.current_time,
                event_type="SHOCK",
                description=f"⚡ TOXIC SHOCK! Fair price jumped {'+' if shock>0 else ''}${shock:.2f} to ${self.fair_price:.2f}",
            ))

        # 2. MM Auto-Quotes if enabled
        if auto_quote:
            bid, ask, res_p = self.mm.compute_quotes(self.fair_price)
            q_events = self.update_mm_quotes(bid, ask, quote_size=5.0)
            events.extend(q_events)

        # 3. Simulate Incoming Taker Flow
        # Arrival rate depends on flow regime
        flow_prob = 0.70
        if random.random() < flow_prob:
            # Determine buy vs sell market order direction
            if self.flow_regime == FlowRegime.TOXIC and abs(shock) > 0.001:
                # Informed traders trade heavily in direction of shock!
                taker_side = Side.BUY if shock > 0 else Side.SELL
                taker_qty = random.choice([5.0, 10.0, 15.0])
                taker_name = "InformedWhale"
            elif self.flow_regime == FlowRegime.MOMENTUM:
                taker_side = Side.BUY if random.random() < 0.65 else Side.SELL
                taker_qty = random.choice([3.0, 5.0, 8.0])
                taker_name = "MomentumTaker"
            else:
                taker_side = Side.BUY if random.random() < 0.50 else Side.SELL
                taker_qty = random.choice([2.0, 5.0, 8.0])
                taker_name = "RetailNoise"

            trades, unfilled = self.book.execute_market_order(
                trader_id=taker_name,
                side=taker_side,
                quantity=taker_qty,
                timestamp=self.current_time,
            )

            for trade in trades:
                # If MM order was filled:
                if trade.maker_trader_id == self.mm.trader_id:
                    self.mm.on_fill(trade, self.fair_price)
                    is_buy = trade.maker_side == Side.BUY
                    side_str = "BUY" if is_buy else "SELL"
                    spread_gain = (self.fair_price - trade.price) if is_buy else (trade.price - self.fair_price)
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=(
                            f"🎯 MM FILLED! {taker_name} {taker_side.value} executed against our {side_str} "
                            f"({trade.quantity} @ ${trade.price:.2f}). Spread Gain: ${spread_gain:.3f}. "
                            f"New Inventory: {self.mm.inventory:+.0f}"
                        ),
                        details={"trade": trade, "spread_gain": spread_gain},
                    ))
                else:
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=f"Market Trade: {taker_name} {taker_side.value} {trade.quantity} @ ${trade.price:.2f}",
                    ))

        # 4. Replenish background liquidity if book gets thin
        bb, ba = self.book.best_bid(), self.book.best_ask()
        if bb is None or ba is None or (ba - bb) > (self.tick_size * 8):
            self._seed_background_liquidity()

        self.recent_events = events + self.recent_events[:40]
        return events
