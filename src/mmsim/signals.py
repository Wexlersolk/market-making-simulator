"""Microstructure Signals, Order Book Imbalance, Micro-Price, and Market Consensus.

Why Microstructure Consensus Matters to Market Makers:
1. Naive Mid Price: (Best Bid + Best Ask) / 2 treats a book with 100 bids and 1 ask as equal.
2. Micro-Price (Stoikov, 2018):
   P_micro = (V_bid * P_ask + V_ask * P_bid) / (V_bid + V_ask)
   When bid volume is huge, micro-price moves toward the ask, anticipating an imminent upward breakout.
3. Order Book Imbalance (OBI):
   OBI = (V_bid - V_ask) / (V_bid + V_ask) in [-1, +1]
   Strong predictive power for next-tick price direction.
4. Composite Fair Value Consensus:
   Blends LOB depth skew, recent trade tape VWAP, and micro-price into an institutional consensus metric.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from mmsim.orderbook import OrderBook
from mmsim.types import Trade


class ConsensusRegime(Enum):
    STRONG_BUY = "STRONG BUY PRESSURE"
    LEAN_BUY = "LEAN BUY"
    BALANCED = "BALANCED CONSENSUS"
    LEAN_SELL = "LEAN SELL"
    STRONG_SELL = "STRONG SELL PRESSURE"


@dataclass
class MarketConsensus:
    mid_price: float
    micro_price: float
    consensus_fair_value: float
    order_book_imbalance: float       # OBI in [-1.0, 1.0]
    total_bid_volume: float
    total_ask_volume: float
    regime: ConsensusRegime
    confidence_pct: float
    skew_direction: str               # "UP", "DOWN", "FLAT"


class MicrostructureSignalEngine:
    """Computes high-frequency predictive signals and market consensus from LOB and tape."""

    def __init__(self, depth_levels: int = 5):
        self.depth_levels = depth_levels

    def compute_imbalance(self, book: OrderBook) -> float:
        """Compute Order Book Imbalance (OBI) across top N price levels."""
        bid_depth, ask_depth = book.get_depth(max_levels=self.depth_levels)
        tot_b = sum(v for _, v in bid_depth)
        tot_a = sum(v for _, v in ask_depth)

        if tot_b + tot_a <= 1e-9:
            return 0.0
        return round((tot_b - tot_a) / (tot_b + tot_a), 4)

    def compute_micro_price(self, book: OrderBook) -> Optional[float]:
        """Compute volume-weighted micro-price (Stoikov formulation)."""
        bb = book.best_bid()
        ba = book.best_ask()
        if bb is None or ba is None:
            return None

        # Level 1 volume
        bids, asks = book.get_depth(max_levels=1)
        if not bids or not asks:
            return book.mid_price()

        vb = bids[0][1]
        va = asks[0][1]

        if vb + va <= 1e-9:
            return book.mid_price()

        # Volume-weighted mid: pushes toward ask if bid volume is larger
        micro = (vb * ba + va * bb) / (vb + va)
        return round(micro, 4)

    def evaluate_consensus(
        self, book: OrderBook, recent_trades: Optional[list[Trade]] = None
    ) -> Optional[MarketConsensus]:
        """Synthesize multi-source order book dynamics into institutional market consensus."""
        mid = book.mid_price()
        if mid is None:
            return None

        micro = self.compute_micro_price(book) or mid
        obi = self.compute_imbalance(book)

        bid_depth, ask_depth = book.get_depth(max_levels=self.depth_levels)
        tot_b = sum(v for _, v in bid_depth)
        tot_a = sum(v for _, v in ask_depth)

        # Recent Trade VWAP adjustment
        trade_bias = 0.0
        if recent_trades:
            recent_window = recent_trades[-10:]
            vol_sum = sum(t.quantity for t in recent_window)
            if vol_sum > 0:
                vwap = sum(t.price * t.quantity for t in recent_window) / vol_sum
                trade_bias = (vwap - mid) * 0.3

        # Composite Consensus Fair Value
        # 60% Micro-price, 30% Mid-price, 10% Trade VWAP
        consensus_fv = round(0.60 * micro + 0.30 * mid + (mid + trade_bias) * 0.10, 4)

        # Determine Regime & Confidence
        if obi > 0.40:
            regime = ConsensusRegime.STRONG_BUY
            confidence = min(98.0, 50.0 + abs(obi) * 50.0)
            skew = "UP"
        elif obi > 0.15:
            regime = ConsensusRegime.LEAN_BUY
            confidence = 50.0 + abs(obi) * 35.0
            skew = "UP"
        elif obi < -0.40:
            regime = ConsensusRegime.STRONG_SELL
            confidence = min(98.0, 50.0 + abs(obi) * 50.0)
            skew = "DOWN"
        elif obi < -0.15:
            regime = ConsensusRegime.LEAN_SELL
            confidence = 50.0 + abs(obi) * 35.0
            skew = "DOWN"
        else:
            regime = ConsensusRegime.BALANCED
            confidence = max(20.0, 50.0 - abs(obi) * 50.0)
            skew = "FLAT"

        return MarketConsensus(
            mid_price=mid,
            micro_price=micro,
            consensus_fair_value=consensus_fv,
            order_book_imbalance=obi,
            total_bid_volume=round(tot_b, 1),
            total_ask_volume=round(tot_a, 1),
            regime=regime,
            confidence_pct=round(confidence, 1),
            skew_direction=skew,
        )
