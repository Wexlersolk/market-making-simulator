import math
import pytest
from mmsim.order_flow import FlowConfig, PoissonOrderFlow
from mmsim.types import OrderType, Side


def test_poisson_interarrival_statistical_mean():
    rate = 10.0  # 10 arrivals per second -> mean interarrival = 0.1s
    flow = PoissonOrderFlow(FlowConfig(market_order_rate=rate))

    samples = [flow.sample_interarrival_time(rate) for _ in range(2000)]
    mean_delay = sum(samples) / len(samples)

    # Expected value is 1 / rate = 0.10, allow 15% tolerance on 2000 samples
    assert math.isclose(mean_delay, 0.10, rel_tol=0.15)


def test_market_and_limit_order_generation():
    flow = PoissonOrderFlow()
    t = 10.0

    # Next market order
    arr_t, mkt_order = flow.next_market_order(timestamp=t, buy_prob=1.0)
    assert arr_t > t
    assert mkt_order.order_type == OrderType.MARKET
    assert mkt_order.side == Side.BUY
    assert mkt_order.quantity >= 1.0

    # Next limit order
    arr_l, lmt_order = flow.next_limit_order(timestamp=t, mid_price=100.0, tick_size=0.05)
    assert arr_l > t
    assert lmt_order.order_type == OrderType.LIMIT
    assert lmt_order.price > 0.0
    assert lmt_order.quantity >= 1.0
