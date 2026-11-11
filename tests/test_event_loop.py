import pytest
from mmsim.event_loop import EventLoop, EventType


def test_event_loop_chronological_ordering():
    loop = EventLoop(start_time=0.0)
    executed = []

    # Insert events out of chronological order
    loop.schedule(delay=0.5, event_type=EventType.STRATEGY_TIMER, data="Event 2")
    loop.schedule(delay=0.1, event_type=EventType.ORDER_ARRIVAL, data="Event 1")
    loop.schedule(delay=1.0, event_type=EventType.EXTERNAL_FLOW, data="Event 3")

    assert len(loop) == 3
    assert loop.peek_next_time() == 0.1

    # Step through
    e1 = loop.step()
    assert e1.data == "Event 1"
    assert loop.current_time == 0.1

    e2 = loop.step()
    assert e2.data == "Event 2"
    assert loop.current_time == 0.5

    e3 = loop.step()
    assert e3.data == "Event 3"
    assert loop.current_time == 1.0

    assert loop.is_empty()


def test_event_loop_run_until_and_handlers():
    loop = EventLoop(start_time=0.0)
    ticks_received = []

    loop.register_handler(
        EventType.MARKET_DATA_TICK,
        lambda ev: ticks_received.append((ev.timestamp, ev.data)),
    )

    loop.schedule(delay=0.2, event_type=EventType.MARKET_DATA_TICK, data="Tick 1")
    loop.schedule(delay=0.4, event_type=EventType.MARKET_DATA_TICK, data="Tick 2")
    loop.schedule(delay=0.8, event_type=EventType.MARKET_DATA_TICK, data="Tick 3")

    # Run up to t = 0.5 (should execute 2 events, leave 3rd)
    processed = loop.run_until(end_time=0.5)
    assert processed == 2
    assert len(ticks_received) == 2
    assert ticks_received[0] == (0.2, "Tick 1")
    assert ticks_received[1] == (0.4, "Tick 2")
    assert loop.current_time == 0.5
    assert len(loop) == 1
