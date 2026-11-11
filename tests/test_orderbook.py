import pytest
from mmsim.doubly_linked_list import OrderList, OrderNode
from mmsim.orderbook import OrderBook
from mmsim.types import Order, OrderType, Side


def test_doubly_linked_list_pointer_manipulation():
    """Verify O(1) unlinking of head, tail, and middle nodes without traversing."""
    ol = OrderList(price=100.0)
    o1 = Order("O1", "TraderA", Side.BUY, 100.0, 5.0, timestamp=1.0)
    o2 = Order("O2", "TraderB", Side.BUY, 100.0, 10.0, timestamp=2.0)
    o3 = Order("O3", "TraderC", Side.BUY, 100.0, 15.0, timestamp=3.0)

    n1 = ol.append(o1)
    n2 = ol.append(o2)
    n3 = ol.append(o3)

    assert ol.count == 3
    assert ol.total_volume == 30.0
    assert ol.head is n1
    assert ol.tail is n3
    assert n2.prev is n1
    assert n2.next is n3

    # Remove middle node (n2) in O(1)
    removed_o2 = ol.remove(n2)
    assert removed_o2.order_id == "O2"
    assert ol.count == 2
    assert ol.total_volume == 20.0
    assert n1.next is n3
    assert n3.prev is n1

    # Remove head (n1) in O(1)
    ol.remove(n1)
    assert ol.head is n3
    assert ol.tail is n3
    assert n3.prev is None

    # Remove remaining tail (n3) in O(1)
    ol.remove(n3)
    assert ol.is_empty()
    assert ol.head is None
    assert ol.tail is None
    assert ol.total_volume == 0.0


def test_orderbook_o1_cancel_and_cached_top_of_book():
    """Verify O(1) cached top of book and O(1) order cancellation."""
    book = OrderBook(tick_size=0.01)

    # Empty book
    assert book.best_bid() is None
    assert book.best_ask() is None

    # Add bids
    book.add_limit_order(Order("B1", "T1", Side.BUY, 99.50, 10.0, timestamp=1.0))
    book.add_limit_order(Order("B2", "T2", Side.BUY, 99.60, 5.0, timestamp=2.0))
    book.add_limit_order(Order("B3", "T3", Side.BUY, 99.40, 20.0, timestamp=3.0))

    # Add asks
    book.add_limit_order(Order("A1", "T1", Side.SELL, 100.10, 8.0, timestamp=1.0))
    book.add_limit_order(Order("A2", "T2", Side.SELL, 100.05, 12.0, timestamp=2.0))

    # Check cached top of book
    assert book.best_bid() == 99.60
    assert book.best_ask() == 100.05
    assert book.spread() == 0.45
    assert book.mid_price() == 99.825

    # Cancel highest bid (B2) -> best bid should immediately fall back to 99.50
    cancelled = book.cancel_order("B2")
    assert cancelled is not None
    assert cancelled.order_id == "B2"
    assert book.best_bid() == 99.50

    # Cancel lowest ask (A2) -> best ask should immediately fall back to 100.10
    book.cancel_order("A2")
    assert book.best_ask() == 100.10
    assert book.spread() == 0.60


def test_orderbook_fifo_queue_priority_and_matching():
    """Verify strict FIFO price-time execution: earlier order fills first at same price."""
    book = OrderBook(tick_size=0.01)

    o1 = Order("O1", "TraderA", Side.BUY, 100.0, 10.0, timestamp=1.0)
    o2 = Order("O2", "TraderB", Side.BUY, 100.0, 5.0, timestamp=2.0)
    book.add_limit_order(o1)
    book.add_limit_order(o2)

    # Queue inspection
    assert book.get_queue_position("O1") == (0, 0.0)
    assert book.get_queue_position("O2") == (1, 10.0)

    # Market sell order for 12 units
    trades, unfilled = book.execute_market_order("Taker", Side.SELL, 12.0, timestamp=3.0)

    assert len(trades) == 2
    assert trades[0].maker_order_id == "O1"
    assert trades[0].quantity == 10.0
    assert trades[1].maker_order_id == "O2"
    assert trades[1].quantity == 2.0
    assert unfilled == 0.0

    # O2 has 3 units remaining and is now at head of line
    assert book.get_queue_position("O2") == (0, 0.0)
