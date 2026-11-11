"""High-Performance Limit Order Book (LOB) with O(1) Cancels and O(1) Top of Book.

Architecture Details:
1. Doubly Linked List per Price Level (`OrderList`):
   - Orders maintain strict FIFO priority.
   - Removing an order from the middle of the queue during cancellation takes O(1) time
     by unlinking node pointers.
2. Order Hash Map (`_orders: dict[str, OrderNode]`):
   - Maps `order_id -> OrderNode` for O(1) order lookup and cancellation.
3. Sorted Price Levels (`SortedDict`):
   - Price levels are kept in sorted order.
   - Bids: descending (best bid is highest price).
   - Asks: ascending (best ask is lowest price).
4. Cached Top of Book:
   - `_cached_best_bid` and `_cached_best_ask` are cached and updated only on level creation/exhaustion.
   - Access to best bid, best ask, mid price, and spread is strictly O(1).
"""

from typing import Optional
import uuid
from sortedcontainers import SortedDict

from mmsim.doubly_linked_list import OrderList, OrderNode
from mmsim.types import Order, OrderType, Side, Trade


class OrderBook:
    """Continuous double auction order book with FIFO priority and O(1) cancels."""

    def __init__(self, tick_size: float = 0.01):
        self.tick_size = tick_size
        # price -> OrderList
        self._bids: SortedDict[float, OrderList] = SortedDict()
        self._asks: SortedDict[float, OrderList] = SortedDict()
        # order_id -> OrderNode (enables O(1) lookup and O(1) unlink)
        self._orders: dict[str, OrderNode] = {}
        self._trade_counter: int = 0

        # O(1) cached top of book
        self._cached_best_bid: Optional[float] = None
        self._cached_best_ask: Optional[float] = None

    def _round_price(self, price: float) -> float:
        return round(round(price / self.tick_size) * self.tick_size, 8)

    def _next_trade_id(self) -> str:
        self._trade_counter += 1
        return f"T{self._trade_counter:07d}"

    def _update_cached_best_bid(self):
        """Update cached best bid using SortedDict peekitem in O(1)."""
        if self._bids:
            # Last key in SortedDict is highest price (best bid)
            self._cached_best_bid = self._bids.peekitem(-1)[0]
        else:
            self._cached_best_bid = None

    def _update_cached_best_ask(self):
        """Update cached best ask using SortedDict peekitem in O(1)."""
        if self._asks:
            # First key in SortedDict is lowest price (best ask)
            self._cached_best_ask = self._asks.peekitem(0)[0]
        else:
            self._cached_best_ask = None

    def best_bid(self) -> Optional[float]:
        """O(1) read of best bid."""
        return self._cached_best_bid

    def best_ask(self) -> Optional[float]:
        """O(1) read of best ask."""
        return self._cached_best_ask

    def spread(self) -> Optional[float]:
        """O(1) read of bid-ask spread."""
        bb, ba = self._cached_best_bid, self._cached_best_ask
        if bb is not None and ba is not None:
            return round(ba - bb, 8)
        return None

    def mid_price(self) -> Optional[float]:
        """O(1) read of mid-market price."""
        bb, ba = self._cached_best_bid, self._cached_best_ask
        if bb is not None and ba is not None:
            return round((ba + bb) / 2.0, 8)
        return None

    def add_limit_order(self, order: Order) -> list[Trade]:
        """Insert limit order. Crosses opposite book if marketable, else posts to queue in O(1)."""
        trades: list[Trade] = []
        price = self._round_price(order.price)
        order.price = price

        if order.side == Side.BUY:
            # Match against asks while marketable (incoming buy price >= best ask)
            while order.quantity > 0 and self._asks:
                best_ask = self.best_ask()
                if best_ask is None or price < best_ask:
                    break

                trades.extend(self._match_level(self._asks, best_ask, order, Side.SELL))
                self._update_cached_best_ask()

            # Rest posted if quantity remains
            if order.quantity > 0:
                if price not in self._bids:
                    self._bids[price] = OrderList(price)
                node = self._bids[price].append(order)
                self._orders[order.order_id] = node
                self._update_cached_best_bid()

        else:  # Side.SELL
            # Match against bids while marketable (incoming sell price <= best bid)
            while order.quantity > 0 and self._bids:
                best_bid = self.best_bid()
                if best_bid is None or price > best_bid:
                    break

                trades.extend(self._match_level(self._bids, best_bid, order, Side.BUY))
                self._update_cached_best_bid()

            # Rest posted if quantity remains
            if order.quantity > 0:
                if price not in self._asks:
                    self._asks[price] = OrderList(price)
                node = self._asks[price].append(order)
                self._orders[order.order_id] = node
                self._update_cached_best_ask()

        return trades

    def execute_market_order(
        self, trader_id: str, side: Side, quantity: float, timestamp: float
    ) -> tuple[list[Trade], float]:
        """Execute market order against resting liquidity. Returns (trades, unfilled_qty)."""
        trades: list[Trade] = []
        pseudo_order = Order(
            order_id=f"MKT_{uuid.uuid4().hex[:8]}",
            trader_id=trader_id,
            side=side,
            price=0.0,
            quantity=quantity,
            timestamp=timestamp,
            order_type=OrderType.MARKET,
        )

        book = self._asks if side == Side.BUY else self._bids
        maker_side = Side.SELL if side == Side.BUY else Side.BUY

        while pseudo_order.quantity > 0 and book:
            best_px = self.best_ask() if side == Side.BUY else self.best_bid()
            if best_px is None:
                break

            matched_trades = self._match_level(book, best_px, pseudo_order, maker_side)
            trades.extend(matched_trades)

            if side == Side.BUY:
                self._update_cached_best_ask()
            else:
                self._update_cached_best_bid()

        return trades, pseudo_order.quantity

    def _match_level(
        self,
        book: SortedDict[float, OrderList],
        level_price: float,
        taker_order: Order,
        maker_side: Side,
    ) -> list[Trade]:
        """Match incoming taker against resting orders at single price level (FIFO)."""
        trades: list[Trade] = []
        order_list = book[level_price]

        while not order_list.is_empty() and taker_order.quantity > 0:
            maker_node = order_list.head
            if maker_node is None:
                break
            maker = maker_node.order
            matched_qty = min(maker.quantity, taker_order.quantity)

            trade = Trade(
                trade_id=self._next_trade_id(),
                maker_order_id=maker.order_id,
                taker_order_id=taker_order.order_id,
                maker_trader_id=maker.trader_id,
                taker_trader_id=taker_order.trader_id,
                price=level_price,
                quantity=matched_qty,
                timestamp=taker_order.timestamp,
                maker_side=maker_side,
            )
            trades.append(trade)

            maker.quantity -= matched_qty
            order_list.total_volume = round(max(0.0, order_list.total_volume - matched_qty), 8)
            taker_order.quantity -= matched_qty

            if maker.quantity <= 1e-10:
                # Fully filled: remove node from list in O(1)
                order_list.remove(maker_node)
                self._orders.pop(maker.order_id, None)

        if order_list.is_empty():
            del book[level_price]

        return trades

    def cancel_order(self, order_id: str) -> Optional[Order]:
        """Cancel resting order by ID in strictly O(1) time using doubly linked list unlinking."""
        node = self._orders.pop(order_id, None)
        if node is None or node.parent_list is None:
            return None

        price_level = node.parent_list
        cancelled_order = price_level.remove(node)

        price = cancelled_order.price
        book = self._bids if cancelled_order.side == Side.BUY else self._asks

        if price_level.is_empty():
            if price in book:
                del book[price]
            if cancelled_order.side == Side.BUY:
                self._update_cached_best_bid()
            else:
                self._update_cached_best_ask()

        return cancelled_order

    def get_queue_position(self, order_id: str) -> Optional[tuple[int, float]]:
        """Return (orders_ahead, volume_ahead) in FIFO queue for specified order."""
        node = self._orders.get(order_id)
        if node is None or node.parent_list is None:
            return None

        orders_ahead = 0
        volume_ahead = 0.0

        curr = node.parent_list.head
        while curr is not None and curr is not node:
            orders_ahead += 1
            volume_ahead += curr.order.quantity
            curr = curr.next

        return orders_ahead, round(volume_ahead, 8)

    def get_depth(
        self, max_levels: int = 10
    ) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """Return aggregated (bids, asks) price levels up to max_levels."""
        # Bids: descending (highest prices first)
        bids = [
            (price, self._bids[price].total_volume)
            for price in reversed(self._bids.keys())
        ][:max_levels]

        # Asks: ascending (lowest prices first)
        asks = [
            (price, self._asks[price].total_volume)
            for price in self._asks.keys()
        ][:max_levels]

        return bids, asks

    def get_level_orders(self, side: Side, price: float) -> list[Order]:
        """Get copy of order queue at specific price level."""
        p = self._round_price(price)
        book = self._bids if side == Side.BUY else self._asks
        order_list = book.get(p)
        return list(order_list) if order_list else []
