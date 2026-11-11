import pytest
from mmsim.market_maker import MarketMaker
from mmsim.simulation import MarketSimulator, FlowRegime
from mmsim.types import Side, Trade


def test_market_maker_fill_and_pnl():
    mm = MarketMaker(trader_id="MM_TEST")

    # Maker BUY filled at $99.90 when mid is $100.00
    trade_buy = Trade(
        trade_id="T1",
        maker_order_id="M1",
        taker_order_id="TK1",
        maker_trader_id="MM_TEST",
        taker_trader_id="TakerA",
        price=99.90,
        quantity=5.0,
        timestamp=1.0,
        maker_side=Side.BUY,
    )
    mm.on_fill(trade_buy, current_mid=100.00)

    assert mm.inventory == 5.0
    assert mm.cash == - (99.90 * 5.0)
    assert round(mm.spread_pnl, 2) == 0.50  # ($100 - $99.90) * 5
    # Mark to market at $100: cash (-499.50) + 5 * 100 (+500) = +0.50
    assert round(mm.mark_to_market_pnl(100.00), 2) == 0.50

    # Maker SELL filled at $100.10 when mid is $100.00
    trade_sell = Trade(
        trade_id="T2",
        maker_order_id="M2",
        taker_order_id="TK2",
        maker_trader_id="MM_TEST",
        taker_trader_id="TakerB",
        price=100.10,
        quantity=5.0,
        timestamp=2.0,
        maker_side=Side.SELL,
    )
    mm.on_fill(trade_sell, current_mid=100.00)

    assert mm.inventory == 0.0
    assert round(mm.spread_pnl, 2) == 1.00
    assert round(mm.mark_to_market_pnl(100.00), 2) == 1.00


def test_simulator_step_execution():
    sim = MarketSimulator(initial_price=100.0, tick_size=0.05, flow_regime=FlowRegime.NOISE)
    assert sim.book.best_bid() is not None
    assert sim.book.best_ask() is not None

    events = sim.step(auto_quote=True)
    assert sim.step_count == 1
    assert len(sim.recent_events) > 0
