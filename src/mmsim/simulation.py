"""Market Simulation Engine with Noise, Momentum, and Toxic Flow regimes."""

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mmsim.latency import LatencyProfile
from mmsim.market_maker import MarketMaker
from mmsim.orderbook import OrderBook
from mmsim.strategy import FixedSpreadStrategy
from mmsim.types import Order, Side


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
    """Simulates market environment with background liquidity, latency, and taker flow.

    Also maintains a parallel FixedSpreadStrategy baseline on identical price path
    and order flow for A/B strategy comparison.
    """

    def __init__(
        self,
        initial_price: float = 100.0,
        tick_size: float = 0.05,
        volatility: float = 0.15,
        flow_regime: FlowRegime = FlowRegime.NOISE,
        latency_profile: Optional[LatencyProfile] = None,
    ):
        self.tick_size = tick_size
        self.fair_price = initial_price
        self.volatility = volatility
        self.flow_regime = flow_regime
        self.latency = latency_profile or LatencyProfile(feed_latency_ms=1.0, order_latency_ms=1.0, jitter_std_ms=0.2)

        self.book = OrderBook(tick_size=tick_size)
        self.mm = MarketMaker(trader_id="MM_USER")

        # Parallel A/B Baseline (Fixed Spread, zero inventory skew)
        self.baseline_book = OrderBook(tick_size=tick_size)
        self.baseline_mm = MarketMaker(trader_id="MM_FIXED")
        self.baseline_strategy = FixedSpreadStrategy(spread_ticks=4, tick_size=tick_size)

        self.step_count = 0
        self.current_time = 0.0
        self.recent_events: list[SimEvent] = []
        self.stale_snipe_count = 0

        # Seed both books identically
        self._seed_background_liquidity(self.book, mirror_book=self.baseline_book)

    def _round_price(self, price: float) -> float:
        return round(round(price / self.tick_size) * self.tick_size, 4)

    def _seed_background_liquidity(self, book: Optional[OrderBook] = None, mirror_book: Optional[OrderBook] = None):
        """Place realistic background limit orders around fair price."""
        target_book = book or self.book
        for i in range(1, 10):
            bp = self._round_price(self.fair_price - i * self.tick_size * 2)
            ap = self._round_price(self.fair_price + i * self.tick_size * 2)
            b_qty = round(random.uniform(5, 25), 0)
            a_qty = round(random.uniform(5, 25), 0)

            b_id = f"BG_B_{i}_{uuid.uuid4().hex[:4]}"
            a_id = f"BG_A_{i}_{uuid.uuid4().hex[:4]}"
            target_book.add_limit_order(Order(b_id, "OtherLP", Side.BUY, bp, b_qty, self.current_time))
            target_book.add_limit_order(Order(a_id, "OtherLP", Side.SELL, ap, a_qty, self.current_time))

            if mirror_book is not None:
                mirror_book.add_limit_order(Order(f"BL_{b_id}", "OtherLP", Side.BUY, bp, b_qty, self.current_time))
                mirror_book.add_limit_order(Order(f"BL_{a_id}", "OtherLP", Side.SELL, ap, a_qty, self.current_time))

    def _place_quotes_on_book(
        self,
        book: OrderBook,
        mm: MarketMaker,
        bid_price: float,
        ask_price: float,
        quote_size: float,
        prefix: str,
    ) -> list[SimEvent]:
        events: list[SimEvent] = []

        if mm.active_bid_id:
            book.cancel_order(mm.active_bid_id)
            mm.active_bid_id = None
        if mm.active_ask_id:
            book.cancel_order(mm.active_ask_id)
            mm.active_ask_id = None

        bid_p = self._round_price(bid_price)
        ask_p = self._round_price(ask_price)

        if bid_p < ask_p:
            bid_id = f"{prefix}_BID_{self.step_count}"
            bid_order = Order(
                order_id=bid_id,
                trader_id=mm.trader_id,
                side=Side.BUY,
                price=bid_p,
                quantity=quote_size,
                timestamp=self.current_time,
                is_mm=True,
            )
            t_bid = book.add_limit_order(bid_order)
            mm.active_bid_id = bid_id

            ask_id = f"{prefix}_ASK_{self.step_count}"
            ask_order = Order(
                order_id=ask_id,
                trader_id=mm.trader_id,
                side=Side.SELL,
                price=ask_p,
                quantity=quote_size,
                timestamp=self.current_time,
                is_mm=True,
            )
            t_ask = book.add_limit_order(ask_order)
            mm.active_ask_id = ask_id

            for trade in t_bid + t_ask:
                if trade.maker_trader_id == mm.trader_id:
                    mm.on_fill(trade, self.fair_price)
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=f"MM Quote instantly crossed! Filled {trade.quantity} @ ${trade.price:.2f}",
                        details={"trade": trade},
                    ))

        return events

    def update_mm_quotes(self, bid_price: float, ask_price: float, quote_size: float = 5.0) -> list[SimEvent]:
        """Cancel old MM quotes and place new quotes."""
        return self._place_quotes_on_book(self.book, self.mm, bid_price, ask_price, quote_size, "MM")

    def _update_baseline_quotes(self, quote_size: float = 5.0):
        """Update parallel FixedSpreadStrategy quotes on baseline_book."""
        half = (self.baseline_strategy.spread_ticks / 2.0) * self.tick_size
        bid = self._round_price(self.fair_price - half)
        ask = self._round_price(self.fair_price + half)
        self._place_quotes_on_book(self.baseline_book, self.baseline_mm, bid, ask, quote_size, "BL")

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
            drift = 0.04
        elif self.flow_regime == FlowRegime.TOXIC:
            if random.random() < 0.15:
                direction = random.choice([-1, 1])
                shock = direction * (self.tick_size * random.randint(4, 10))

        price_step = (drift * dt) + (self.volatility * (dt ** 0.5) * random.gauss(0, 1)) + shock
        self.fair_price = round(max(self.fair_price + price_step, self.tick_size * 5), 4)

        if abs(shock) > 0.001:
            events.append(SimEvent(
                timestamp=self.current_time,
                event_type="SHOCK",
                description=f"TOXIC SHOCK! Fair price jumped {'+' if shock>0 else ''}${shock:.2f} to ${self.fair_price:.2f}",
            ))

        # 2. Check Network Latency (Feed + Order transit vs 50ms tick window)
        sampled_rtt_ms = (self.latency.sample_feed_latency_sec() + self.latency.sample_order_latency_sec()) * 1000.0
        quote_delayed = auto_quote and (self.step_count > 1) and (random.random() < min(0.92, max(0.0, (sampled_rtt_ms - 2.0) / 100.0)))

        # If NOT delayed, MM updates quotes BEFORE incoming taker flow arrives
        if auto_quote and not quote_delayed:
            bid, ask, _ = self.mm.compute_quotes(self.fair_price)
            q_events = self.update_mm_quotes(bid, ask, quote_size=5.0)
            events.extend(q_events)
            self._update_baseline_quotes(quote_size=5.0)

        # 3. Simulate Incoming Taker Flow
        flow_prob = 0.70
        if random.random() < flow_prob:
            if self.flow_regime == FlowRegime.TOXIC and abs(shock) > 0.001:
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

            # Execute on primary book
            trades, _ = self.book.execute_market_order(
                trader_id=taker_name,
                side=taker_side,
                quantity=taker_qty,
                timestamp=self.current_time,
            )

            for trade in trades:
                if trade.maker_trader_id == self.mm.trader_id:
                    self.mm.on_fill(trade, self.fair_price)
                    is_buy = trade.maker_side == Side.BUY
                    side_str = "BUY" if is_buy else "SELL"
                    spread_gain = (self.fair_price - trade.price) if is_buy else (trade.price - self.fair_price)
                    stale_tag = ""
                    if quote_delayed:
                        self.stale_snipe_count += 1
                        stale_tag = f" [STALE QUOTE SNIPED @ {sampled_rtt_ms:.0f}ms!]"
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=(
                            f"MM FILLED{stale_tag} {taker_name} {taker_side.value} hit {side_str} "
                            f"({trade.quantity} @ ${trade.price:.2f}). Edge: ${spread_gain:+.3f} | Inv: {self.mm.inventory:+.0f}"
                        ),
                        details={"trade": trade, "spread_gain": spread_gain, "stale_snipe": quote_delayed},
                    ))
                else:
                    events.append(SimEvent(
                        timestamp=self.current_time,
                        event_type="TRADE",
                        description=f"Market Trade: {taker_name} {taker_side.value} {trade.quantity} @ ${trade.price:.2f}",
                    ))

            # Execute identical order on A/B baseline book
            bl_trades, _ = self.baseline_book.execute_market_order(
                trader_id=taker_name,
                side=taker_side,
                quantity=taker_qty,
                timestamp=self.current_time,
            )
            for trade in bl_trades:
                if trade.maker_trader_id == self.baseline_mm.trader_id:
                    self.baseline_mm.on_fill(trade, self.fair_price)

        # If delayed by network latency, MM's new quotes arrive AFTER taker flow
        if auto_quote and quote_delayed:
            bid, ask, _ = self.mm.compute_quotes(self.fair_price)
            q_events = self.update_mm_quotes(bid, ask, quote_size=5.0)
            events.extend(q_events)
            self._update_baseline_quotes(quote_size=5.0)

        # Ensure at least a QUOTE/PRICE_MOVE event is emitted per step
        if not events:
            events.append(SimEvent(
                timestamp=self.current_time,
                event_type="PRICE_MOVE",
                description=f"Fair price tick: ${self.fair_price:.2f}",
            ))

        # 4. Replenish background liquidity if book gets thin
        bb, ba = self.book.best_bid(), self.book.best_ask()
        if bb is None or ba is None or (ba - bb) > (self.tick_size * 8):
            self._seed_background_liquidity(self.book)

        bl_bb, bl_ba = self.baseline_book.best_bid(), self.baseline_book.best_ask()
        if bl_bb is None or bl_ba is None or (bl_ba - bl_bb) > (self.tick_size * 8):
            self._seed_background_liquidity(self.baseline_book)

        self.recent_events = events + self.recent_events[:40]
        return events
