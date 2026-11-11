"""Accounting Engine & PnL Attribution (Spread Capture vs Inventory Risk).

Why PnL Attribution is Critical in Market Making:
1. Total PnL = Cash + Inventory * Current Mid.
2. But is that PnL coming from:
   - Pure spread capture (buying at bid, selling at ask)?
   - Or accidental directional speculation (being long during a bull market)?
3. If a market maker shows high PnL solely because of inventory drift, they are not market making;
   they are taking uncompensated beta risk.
4. This module decomposes every basis point into:
   - Spread PnL (True Market Maker Edge)
   - Mark-to-Market Inventory PnL (Drift & Beta Exposure)
   - Adverse Selection Drift (Post-trade price movement at 1s, 5s)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

from mmsim.types import Side, Trade


@dataclass
class PnLSnapshot:
    timestamp: float
    mid_price: float
    cash: float
    inventory: float
    spread_pnl: float
    inventory_pnl: float
    total_mtm_pnl: float


class Accountant:
    """Tracks portfolio state, transaction history, and performs PnL decomposition."""

    def __init__(self, initial_cash: float = 100_000.0, trader_id: str = "MM_BOT"):
        self.initial_cash: float = initial_cash
        self.trader_id: str = trader_id
        self.cash: float = initial_cash
        self.inventory: float = 0.0

        # PnL Attribution
        self.cumulative_spread_pnl: float = 0.0
        self.trade_history: list[dict] = []
        self.snapshots: list[PnLSnapshot] = []

    def on_fill(self, trade: Trade, mid_at_fill: float, timestamp: float):
        """Record trade execution and attribute spread gain."""
        is_buy = (trade.maker_trader_id == self.trader_id and trade.maker_side == Side.BUY) or \
                 (trade.taker_trader_id == self.trader_id and trade.maker_side == Side.SELL)

        qty = trade.quantity
        px = trade.price

        if is_buy:
            self.inventory += qty
            self.cash -= px * qty
            # Spread gain relative to fair mid
            spread_earned = (mid_at_fill - px) * qty
        else:
            self.inventory -= qty
            self.cash += px * qty
            # Spread gain relative to fair mid
            spread_earned = (px - mid_at_fill) * qty

        self.cumulative_spread_pnl += spread_earned

        self.trade_history.append({
            "trade_id": trade.trade_id,
            "timestamp": timestamp,
            "side": "BUY" if is_buy else "SELL",
            "price": px,
            "quantity": qty,
            "mid_at_fill": mid_at_fill,
            "spread_earned": spread_earned,
            "inventory_after": self.inventory,
            "cash_after": self.cash,
        })

    def snapshot(self, current_mid: float, timestamp: float) -> PnLSnapshot:
        """Calculate exact mark-to-market and attribution at current timestamp."""
        total_pnl = (self.cash - self.initial_cash) + (self.inventory * current_mid)
        inv_pnl = total_pnl - self.cumulative_spread_pnl

        snap = PnLSnapshot(
            timestamp=timestamp,
            mid_price=current_mid,
            cash=self.cash,
            inventory=self.inventory,
            spread_pnl=round(self.cumulative_spread_pnl, 4),
            inventory_pnl=round(inv_pnl, 4),
            total_mtm_pnl=round(total_pnl, 4),
        )
        self.snapshots.append(snap)
        return snap

    def compute_summary_metrics(self) -> dict:
        """Compute performance analytics: Sharpe, Max Drawdown, Win Rate."""
        if not self.snapshots:
            return {}

        pnls = [s.total_mtm_pnl for s in self.snapshots]
        invs = [s.inventory for s in self.snapshots]

        # Drawdown calculation
        peak = pnls[0]
        max_dd = 0.0
        for p in pnls:
            if p > peak:
                peak = p
            dd = peak - p
            if dd > max_dd:
                max_dd = dd

        # Returns Sharpe (discrete intervals)
        returns = [pnls[i] - pnls[i - 1] for i in range(1, len(pnls))]
        if len(returns) > 1:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            std_r = math.sqrt(var_r)
            sharpe = (mean_r / std_r * math.sqrt(252 * 6.5 * 3600)) if std_r > 1e-8 else 0.0
        else:
            sharpe = 0.0

        # Mean inventory & max inventory exposure
        max_inv = max(abs(q) for q in invs) if invs else 0.0
        avg_inv = sum(invs) / len(invs) if invs else 0.0

        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t["spread_earned"] > 0)
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0

        latest = self.snapshots[-1]
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "total_mtm_pnl": latest.total_mtm_pnl,
            "spread_capture_pnl": latest.spread_pnl,
            "inventory_risk_pnl": latest.inventory_pnl,
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_inventory_exposure": max_inv,
            "average_inventory": round(avg_inv, 2),
        }
