import pytest
from mmsim.event_loop import EventLoop, EventType
from mmsim.latency import InFlightRegistry, LatencyProfile
from mmsim.orderbook import OrderBook
from mmsim.types import Order, Side


def test_latency_sampling():
    profile = LatencyProfile(feed_latency_ms=2.0, order_latency_ms=5.0, jitter_std_ms=0.0)
    assert profile.sample_feed_latency_sec() == 0.002
    assert profile.sample_order_latency_sec() == 0.005


def test_cancel_race_condition_simulation():
    """Demonstrate classic HFT cancel race:
    1. MM order resting in book at t = 0.
    2. At t = 1.000, MM detects adverse event and sends CANCEL (5ms latency -> arrives t = 1.005).
    3. At t = 1.001, fast taker fires aggressive market order (2ms latency -> arrives t = 1.003).
    4. Discrete-event loop processes taker at t = 1.003 -> MM quote is FILLED!
    5. Cancel arrives at t = 1.005 -> Order is no longer in book (cancel failed / race lost).
    """
    loop = EventLoop(start_time=0.0)
    book = OrderBook(tick_size=0.01)
    inflight = InFlightRegistry()

    # Resting MM quote
    mm_order = Order("MM_B1", "MM_BOT", Side.BUY, 100.0, 10.0, timestamp=0.0)
    book.add_limit_order(mm_order)

    execution_history = []

    # MM sends cancel at t = 1.000 with 5ms latency
    loop.current_time = 1.000
    inflight.record_cancel_request("MM_B1", timestamp=1.000)

    def handle_cancel_arrival(ev):
        inflight.confirm_cancel_arrival("MM_B1")
        res = book.cancel_order("MM_B1")
        execution_history.append(("CANCEL_RESULT", ev.timestamp, res is not None))

    loop.schedule(delay=0.005, event_type=EventType.CANCEL_ARRIVAL, handler=handle_cancel_arrival)

    # Taker fires market sell at t = 1.001 with 2ms latency (arrives t = 1.003)
    loop.current_time = 1.001

    def handle_taker_arrival(ev):
        trades, unfilled = book.execute_market_order("FastTaker", Side.SELL, 10.0, timestamp=ev.timestamp)
        execution_history.append(("TAKER_FILL", ev.timestamp, len(trades)))

    loop.schedule(delay=0.002, event_type=EventType.ORDER_ARRIVAL, handler=handle_taker_arrival)

    # Run discrete event loop
    loop.run_until(end_time=1.010)

    assert len(execution_history) == 2
    # 1st: Taker arrived at 1.003 and filled MM quote!
    assert execution_history[0] == ("TAKER_FILL", 1.003, 1)
    # 2nd: Cancel arrived at 1.005 and found order already gone!
    assert execution_history[1] == ("CANCEL_RESULT", 1.005, False)
    assert book.best_bid() is None
