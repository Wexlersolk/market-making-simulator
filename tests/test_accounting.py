import pytest
from mmsim.accounting import Accountant
from mmsim.types import Side, Trade


def test_accounting_spread_vs_inventory_decomposition():
    acc = Accountant(initial_cash=10_000.0, trader_id="MM_TEST")

    # Trade 1: MM buys 10 units at $99.90 when mid is $100.00 (half-spread = $0.10)
    t1 = Trade("T1", "MM_O1", "TK1", "MM_TEST", "TakerA", price=99.90, quantity=10.0, timestamp=1.0, maker_side=Side.BUY)
    acc.on_fill(t1, mid_at_fill=100.00, timestamp=1.0)

    assert acc.inventory == 10.0
    assert acc.cash == 10_000.0 - 999.0
    assert round(acc.cumulative_spread_pnl, 2) == 1.00  # 10 * ($100 - $99.90)

    # Snapshot immediately at mid = 100.00
    s1 = acc.snapshot(current_mid=100.00, timestamp=1.0)
    assert s1.spread_pnl == 1.00
    assert s1.inventory_pnl == 0.00
    assert s1.total_mtm_pnl == 1.00

    # Market price drops to $99.00 while MM holds +10 long inventory
    s2 = acc.snapshot(current_mid=99.00, timestamp=2.0)
    # Inventory loss: 10 units * ($99 - $100) = -$10.00
    assert s2.spread_pnl == 1.00
    assert s2.inventory_pnl == -10.00
    # Total PnL = +$1.00 spread - $10.00 inventory = -$9.00
    assert s2.total_mtm_pnl == -9.00
    assert round(s2.spread_pnl + s2.inventory_pnl, 2) == s2.total_mtm_pnl


def test_summary_metrics():
    acc = Accountant(initial_cash=10_000.0, trader_id="MM_TEST")
    t1 = Trade("T1", "M1", "TK1", "MM_TEST", "TakerA", price=99.95, quantity=5.0, timestamp=1.0, maker_side=Side.BUY)
    acc.on_fill(t1, mid_at_fill=100.00, timestamp=1.0)
    acc.snapshot(100.00, 1.0)

    metrics = acc.compute_summary_metrics()
    assert metrics["total_trades"] == 1
    assert metrics["win_rate"] == 1.0
    assert metrics["spread_capture_pnl"] == 0.25
