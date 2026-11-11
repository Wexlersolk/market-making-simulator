"""Discrete-Event Simulation (DES) Engine.

Why Discrete-Event Simulation for High-Frequency Trading?
1. Fixed-time stepping (e.g. dt = 1s) cannot accurately model microsecond network latencies,
   order racing, or queue priority changes.
2. A priority queue (min-heap) allows jumping directly from event to event in exact timestamp order.
3. Every order placed by a trader is scheduled with a future arrival timestamp:
   arrival_time = current_time + network_latency.
"""

from __future__ import annotations
import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class EventType(Enum):
    """Categorization of events traversing the simulation timeline."""
    ORDER_ARRIVAL = auto()       # Order reached exchange matching engine
    CANCEL_ARRIVAL = auto()      # Cancel request reached exchange
    MARKET_DATA_TICK = auto()    # Market data broadcast to participants
    STRATEGY_TIMER = auto()      # Strategy periodic timer / trigger
    EXTERNAL_FLOW = auto()       # Stochastic arrival of external retail/whale orders


@dataclass(order=True)
class Event:
    """Timestamped event ordered strictly by execution time in min-heap."""
    timestamp: float
    seq: int                     # Monotonic sequence counter for heap stability
    event_type: EventType = field(compare=False)
    data: Any = field(default=None, compare=False)
    handler: Optional[Callable[[Event], None]] = field(default=None, compare=False)


class EventLoop:
    """Discrete-event scheduler driving the simulator timeline."""

    def __init__(self, start_time: float = 0.0):
        self.current_time: float = start_time
        self._queue: list[Event] = []
        self._seq: int = 0
        self._handlers: dict[EventType, list[Callable[[Event], None]]] = {
            et: [] for et in EventType
        }

    def register_handler(self, event_type: EventType, handler: Callable[[Event], None]):
        """Register a callback for a specific event type."""
        self._handlers[event_type].append(handler)

    def schedule(
        self,
        delay: float,
        event_type: EventType,
        data: Any = None,
        handler: Optional[Callable[[Event], None]] = None,
    ) -> Event:
        """Schedule an event to fire at `current_time + delay`."""
        if delay < 0:
            raise ValueError(f"Event delay cannot be negative, got {delay}")

        target_time = round(self.current_time + delay, 9)
        self._seq += 1
        event = Event(
            timestamp=target_time,
            seq=self._seq,
            event_type=event_type,
            data=data,
            handler=handler,
        )
        heapq.heappush(self._queue, event)
        return event

    def peek_next_time(self) -> Optional[float]:
        """Return timestamp of next pending event, or None if queue is empty."""
        return self._queue[0].timestamp if self._queue else None

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def step(self) -> Optional[Event]:
        """Pop and execute the single earliest event in the queue."""
        if not self._queue:
            return None

        event = heapq.heappop(self._queue)
        # Advance simulation time directly to event timestamp
        self.current_time = event.timestamp

        # Execute event-specific handler if attached
        if event.handler is not None:
            event.handler(event)

        # Execute registered type handlers
        for h in self._handlers.get(event.event_type, []):
            h(event)

        return event

    def run_until(self, end_time: float) -> int:
        """Process all events up to end_time. Returns count of events processed."""
        processed = 0
        while self._queue and self._queue[0].timestamp <= end_time:
            self.step()
            processed += 1
        if self.current_time < end_time:
            self.current_time = end_time
        return processed

    def __len__(self) -> int:
        return len(self._queue)
