"""Full Discrete-Event Market Making Simulator Orchestrator.

Integrates:
- Limit Order Book (Doubly Linked List O(1) cancels, O(1) top of book)
- Discrete Event Loop (Min-heap priority timeline)
- Network Latency Model (Feed latency, Order routing latency, In-flight state)
- Stochastic Order Flow (Poisson arrivals of market orders and background depth)
- Strategy (Avellaneda-Stoikov inventory skew or FixedSpread baseline)
- Accounting (PnL attribution: spread capture vs inventory risk)
"""

from __future__ import annotations
import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from mmsim.accounting import Accountant
from mmsim.event_loop import Event, EventLoop, EventType
from mmsim.latency import InFlightRegistry, LatencyProfile
from mmsim.order_flow import FlowConfig, PoissonOrderFlow
from mmsim.orderbook import OrderBook
from mmsim.strategy import AvellanedaStoikov, BaseStrategy
from mmsim.types import Order, OrderType, Side, Trade


@dataclass
class SimConfig:
    initial_price: float = 100.0
    tick_size: float = 0.01
    volatility: float = 0.20          # Asset annual/session volatility
    flow_config: FlowConfig = field(default_factory=FlowConfig)
    latency_profile: LatencyProfile = field(default_factory=LatencyProfile)
    strategy_wake_interval: float = 0.1  # Strategy re-evaluates quotes every 100ms
    quote_size: float = 5.0


class Simulator:
    """End-to-end discrete-event market making simulation environment."""

    def __init__(self, config: Optional[SimConfig] = None, strategy: Optional[BaseStrategy] = None):
        self.config = config or SimConfig()
        self.strategy: BaseStrategy = strategy or AvellanedaStoikov(
            tick_size=self.config.tick_size, sigma=self.config.volatility
        )

        self.fair_price: float = self.config.initial_price
        self.book = OrderBook(tick_size=self.config.tick_size)
        self.loop = EventLoop(start_time=0.0)
        self.flow = PoissonOrderFlow(self.config.flow_config)
        self.latency = self.config.latency_profile
        self.inflight = InFlightRegistry()
        self.accountant = Accountant(initial_cash=100_000.0, trader_id="MM_BOT")

        # Active MM quotes resting in book
        self.active_bid_id: Optional[str] = None
        self.active_ask_id: Optional[str] = None
        self.last_bid_price: Optional[float] = None
        self.last_ask_price: Optional[float] = None

        # Telemetry
        self.event_log: list[str] = []

        # Setup event handlers and seed initial book
        self._register_handlers()
        self._seed_initial_liquidity()
        self._schedule_initial_events()

    def _register_handlers(self):
        self.loop.register_handler(EventType.STRATEGY_TIMER, self._on_strategy_timer)
        self.loop.register_handler(EventType.EXTERNAL_FLOW, self._on_external_flow)
        self.loop.register_handler(EventType.MARKET_DATA_TICK, self._on_price_drift_tick)

    def _seed_initial_liquidity(self):
        """Seed initial background orders around fair price."""
        for i in range(1, 8):
            bp = round(self.fair_price - i * self.config.tick_size * 2, 8)
            ap = round(self.fair_price + i * self.config.tick_size * 2, 8)
            self.book.add_limit_order(Order(f"BG_B_{i}", "SeedLP", Side.BUY, bp, 10.0, 0.0))
            self.book.add_limit_order(Order(f"BG_A_{i}", "SeedLP", Side.SELL, ap, 10.0, 0.0))

    def _schedule_initial_events(self):
        # 1. Strategy timer
        self.loop.schedule(self.config.strategy_wake_interval, EventType.STRATEGY_TIMER)
        # 2. External flow
        arr_t, _ = self.flow.next_market_order(self.loop.current_time)
        self.loop.schedule(max(0.001, arr_t - self.loop.current_time), EventType.EXTERNAL_FLOW)
        # 3. Price drift tick
        self.loop.schedule(0.05, EventType.MARKET_DATA_TICK)

    def _on_price_drift_tick(self, event: Event):
        """Brownian motion update to fair latent price."""
        dt = 0.05
        drift = self.config.volatility * (dt ** 0.5) * random.gauss(0, 1)
        self.fair_price = round(max(self.config.tick_size * 5, self.fair_price + drift), 8)

        # Record accounting snapshot
        self.accountant.snapshot(self.fair_price, self.loop.current_time)

        # Schedule next drift tick
        self.loop.schedule(dt, EventType.MARKET_DATA_TICK)

    def _on_strategy_timer(self, event: Event):
        """Market maker strategy generates quotes and sends with routing latency."""
        target_bid, target_ask = self.strategy.generate_quotes(
            self.book, self.accountant.inventory, self.loop.current_time
        )

        should_update = self.strategy.should_requote(
            self.last_bid_price, self.last_ask_price,
            target_bid, target_ask,
            min_move_ticks=1.0, tick_size=self.config.tick_size,
        )

        if should_update and target_bid is not None and target_ask is not None:
            # Latency delay for quote update to reach exchange
            routing_delay = self.latency.sample_order_latency_sec()
            new_bid_id = f"MM_B_{uuid.uuid4().hex[:6]}"
            new_ask_id = f"MM_A_{uuid.uuid4().hex[:6]}"

            old_bid = self.active_bid_id
            old_ask = self.active_ask_id

            def apply_quotes(ev: Event):
                # Cancel old quotes
                if old_bid:
                    self.book.cancel_order(old_bid)
                if old_ask:
                    self.book.cancel_order(old_ask)

                # Post new quotes
                o_bid = Order(
                    new_bid_id, self.accountant.trader_id, Side.BUY, target_bid,
                    self.config.quote_size, ev.timestamp, is_mm=True
                )
                o_ask = Order(
                    new_ask_id, self.accountant.trader_id, Side.SELL, target_ask,
                    self.config.quote_size, ev.timestamp, is_mm=True
                )

                t_b = self.book.add_limit_order(o_bid)
                t_a = self.book.add_limit_order(o_ask)

                self.active_bid_id = new_bid_id
                self.active_ask_id = new_ask_id
                self.last_bid_price = target_bid
                self.last_ask_price = target_ask

                # Process any immediate crosses
                for tr in t_b + t_a:
                    if tr.maker_trader_id == self.accountant.trader_id:
                        self.accountant.on_fill(tr, self.fair_price, ev.timestamp)

            self.loop.schedule(routing_delay, EventType.ORDER_ARRIVAL, handler=apply_quotes)

        # Re-schedule strategy wake up
        self.loop.schedule(self.config.strategy_wake_interval, EventType.STRATEGY_TIMER)

    def _on_external_flow(self, event: Event):
        """Process incoming Poisson market order and match against book."""
        # 50/50 noise taker
        _, mkt_order = self.flow.next_market_order(self.loop.current_time)
        trades, unfilled = self.book.execute_market_order(
            mkt_order.trader_id, mkt_order.side, mkt_order.quantity, self.loop.current_time
        )

        for trade in trades:
            if trade.maker_trader_id == self.accountant.trader_id:
                self.accountant.on_fill(trade, self.fair_price, self.loop.current_time)
                self.event_log.append(
                    f"[{self.loop.current_time:.3f}s] MM FILLED {trade.quantity} @ ${trade.price:.2f} "
                    f"({trade.maker_side.value}). Inv: {self.accountant.inventory:+.0f}"
                )

        # Replenish background depth if spread blew out
        bb, ba = self.book.best_bid(), self.book.best_ask()
        if bb is None or ba is None or (ba - bb) > (self.config.tick_size * 10):
            self._seed_initial_liquidity()

        # Schedule next market order arrival
        next_dt = self.flow.sample_interarrival_time(self.config.flow_config.market_order_rate)
        self.loop.schedule(max(0.001, next_dt), EventType.EXTERNAL_FLOW)

    def run_for(self, duration_seconds: float):
        """Run discrete-event simulation for specified duration."""
        target = self.loop.current_time + duration_seconds
        self.loop.run_until(target)
        self.accountant.snapshot(self.fair_price, self.loop.current_time)
