"""Doubly Linked List for Limit Order Book Price Levels.

Why Doubly Linked List?
- In an order book, orders must maintain strict FIFO priority (time priority).
- Standard Python deque or list requires O(N) to remove an order by ID from the middle of the queue on cancellation.
- A Doubly Linked List node holds pointers to `prev` and `next`.
- By mapping `order_id -> OrderNode` in a hash map, any order can be cancelled and unlinked in strictly O(1) time without traversing the queue.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator, Optional

from mmsim.types import Order


class OrderNode:
    """Node wrapping an Order within a price level's doubly linked list."""

    __slots__ = ("order", "prev", "next", "parent_list")

    def __init__(self, order: Order, parent_list: Optional[OrderList] = None):
        self.order: Order = order
        self.prev: Optional[OrderNode] = None
        self.next: Optional[OrderNode] = None
        self.parent_list: Optional[OrderList] = parent_list


class OrderList:
    """Doubly linked list of orders at a single price level, maintaining FIFO order."""

    __slots__ = ("head", "tail", "count", "total_volume", "price")

    def __init__(self, price: float):
        self.price: float = price
        self.head: Optional[OrderNode] = None
        self.tail: Optional[OrderNode] = None
        self.count: int = 0
        self.total_volume: float = 0.0

    def append(self, order: Order) -> OrderNode:
        """Append an order to the back of the queue in O(1) time."""
        node = OrderNode(order, parent_list=self)
        if self.tail is None:
            # Empty list: new node is both head and tail
            self.head = node
            self.tail = node
        else:
            # Link to existing tail
            self.tail.next = node
            node.prev = self.tail
            self.tail = node

        self.count += 1
        self.total_volume = round(self.total_volume + order.quantity, 8)
        return node

    def remove(self, node: OrderNode) -> Order:
        """Unlink an arbitrary node from the list in strictly O(1) time."""
        if node.parent_list is not self:
            raise ValueError("Node does not belong to this OrderList")

        # Unlink previous pointer
        if node.prev is not None:
            node.prev.next = node.next
        else:
            # Node was head
            self.head = node.next

        # Unlink next pointer
        if node.next is not None:
            node.next.prev = node.prev
        else:
            # Node was tail
            self.tail = node.prev

        self.count -= 1
        self.total_volume = round(max(0.0, self.total_volume - node.order.quantity), 8)

        # Clear node references
        node.prev = None
        node.next = None
        node.parent_list = None
        return node.order

    def popleft(self) -> Optional[Order]:
        """Pop and return the head order (earliest order in queue) in O(1) time."""
        if self.head is None:
            return None
        return self.remove(self.head)

    def is_empty(self) -> bool:
        return self.count == 0

    def __iter__(self) -> Iterator[Order]:
        curr = self.head
        while curr is not None:
            yield curr.order
            curr = curr.next

    def __len__(self) -> int:
        return self.count
