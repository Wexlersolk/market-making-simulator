import pytest
from mmsim.orderbook import OrderBook
from mmsim.strategy import AvellanedaStoikov, FixedSpreadStrategy
from mmsim.types import Order, Side


def test_fixed_spread_strategy():
    strat = FixedSpreadStrategy(spread_ticks=4, tick_size=0.01)
    book = OrderBook(tick_size=0.01)
    book.add_limit_order(Order("B1", "T1", Side.BUY, 99.98, 10.0, 1.0))
    book.add_limit_order(Order("A1", "T2", Side.SELL, 100.02, 10.0, 1.0))

    bid, ask = strat.generate_quotes(book, inventory=5.0, current_time=1.0)
    assert bid == 99.98
    assert ask == 100.02
    assert round(ask - bid, 4) == 0.04


def test_avellaneda_stoikov_inventory_skew():
    model = AvellanedaStoikov(gamma=0.1, sigma=0.2, T=1.0, kappa=1.5, tick_size=0.01)

    # 1. Zero inventory: reservation price == mid price
    r_zero = model.reservation_price(mid_price=100.0, inventory=0.0, t=0.0)
    assert r_zero == 100.0
    bid_0, ask_0, _ = model.optimal_quotes(100.0, inventory=0.0, t=0.0)

    # 2. Long inventory (+10): reservation price drops below mid
    r_long = model.reservation_price(mid_price=100.0, inventory=10.0, t=0.0)
    assert r_long < 100.0
    bid_long, ask_long, _ = model.optimal_quotes(100.0, inventory=10.0, t=0.0)
    assert bid_long < bid_0
    assert ask_long < ask_0

    # 3. Short inventory (-10): reservation price rises above mid
    r_short = model.reservation_price(mid_price=100.0, inventory=-10.0, t=0.0)
    assert r_short > 100.0
    bid_short, ask_short, _ = model.optimal_quotes(100.0, inventory=-10.0, t=0.0)
    assert bid_short > bid_0
    assert ask_short > ask_0


def test_should_requote_threshold():
    strat = AvellanedaStoikov(tick_size=0.01)

    # Move is less than 1 tick (0.005 < 0.01) -> should NOT requote
    assert not strat.should_requote(
        current_bid=100.00, current_ask=100.10,
        target_bid=100.004, target_ask=100.103,
        min_move_ticks=1.0, tick_size=0.01
    )

    # Move is 1 tick or more -> should requote
    assert strat.should_requote(
        current_bid=100.00, current_ask=100.10,
        target_bid=99.99, target_ask=100.10,
        min_move_ticks=1.0, tick_size=0.01
    )
