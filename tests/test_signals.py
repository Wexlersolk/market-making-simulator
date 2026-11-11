import pytest
from mmsim.orderbook import OrderBook
from mmsim.signals import ConsensusRegime, MicrostructureSignalEngine
from mmsim.types import Order, Side


def test_microstructure_signals_balanced_book():
    book = OrderBook(tick_size=0.01)
    book.add_limit_order(Order("B1", "T1", Side.BUY, 99.90, 50.0, 1.0))
    book.add_limit_order(Order("A1", "T2", Side.SELL, 100.10, 50.0, 1.0))

    engine = MicrostructureSignalEngine()
    consensus = engine.evaluate_consensus(book)

    assert consensus is not None
    assert consensus.mid_price == 100.00
    assert consensus.micro_price == 100.00
    assert consensus.order_book_imbalance == 0.0
    assert consensus.regime == ConsensusRegime.BALANCED


def test_microstructure_signals_heavy_buy_skew():
    book = OrderBook(tick_size=0.01)
    # Huge bid volume (90 units @ 99.90), tiny ask volume (10 units @ 100.10)
    book.add_limit_order(Order("B1", "T1", Side.BUY, 99.90, 90.0, 1.0))
    book.add_limit_order(Order("A1", "T2", Side.SELL, 100.10, 10.0, 1.0))

    engine = MicrostructureSignalEngine()
    consensus = engine.evaluate_consensus(book)

    assert consensus is not None
    assert consensus.mid_price == 100.00
    # Micro price is pulled UP toward ask: (90 * 100.10 + 10 * 99.90) / 100 = 100.08
    assert consensus.micro_price > 100.00
    assert consensus.order_book_imbalance == 0.80
    assert consensus.regime == ConsensusRegime.STRONG_BUY
    assert consensus.skew_direction == "UP"


def test_microstructure_signals_heavy_sell_skew():
    book = OrderBook(tick_size=0.01)
    # Tiny bid volume (10 units @ 99.90), huge ask volume (90 units @ 100.10)
    book.add_limit_order(Order("B1", "T1", Side.BUY, 99.90, 10.0, 1.0))
    book.add_limit_order(Order("A1", "T2", Side.SELL, 100.10, 90.0, 1.0))

    engine = MicrostructureSignalEngine()
    consensus = engine.evaluate_consensus(book)

    assert consensus is not None
    # Micro price pulled DOWN toward bid
    assert consensus.micro_price < 100.00
    assert consensus.order_book_imbalance == -0.80
    assert consensus.regime == ConsensusRegime.STRONG_SELL
    assert consensus.skew_direction == "DOWN"
