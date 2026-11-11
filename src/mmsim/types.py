"""Core domain types for Market Making Simulator."""

from dataclasses import dataclass
from enum import Enum, auto


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self == Side.BUY else Side.BUY


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    CANCEL = "CANCEL"


@dataclass(slots=True)
class Order:
    order_id: str
    trader_id: str
    side: Side
    price: float
    quantity: float
    timestamp: float
    order_type: OrderType = OrderType.LIMIT
    is_mm: bool = False

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError(f"Order quantity must be positive, got {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.price <= 0:
            raise ValueError(f"Limit order price must be positive, got {self.price}")


@dataclass(slots=True, frozen=True)
class Trade:
    trade_id: str
    maker_order_id: str
    taker_order_id: str
    maker_trader_id: str
    taker_trader_id: str
    price: float
    quantity: float
    timestamp: float
    maker_side: Side
