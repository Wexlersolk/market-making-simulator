import pytest
from mmsim.accounting import Accountant
from mmsim.simulator import SimConfig, Simulator
from mmsim.strategy import AvellanedaStoikov, FixedSpreadStrategy


def test_simulator_end_to_end_discrete_run():
    config = SimConfig(
        initial_price=100.0,
        tick_size=0.01,
        volatility=0.10,
        strategy_wake_interval=0.1,
    )
    sim = Simulator(config=config, strategy=AvellanedaStoikov(tick_size=0.01))

    # Initial state
    assert sim.book.best_bid() is not None
    assert sim.book.best_ask() is not None
    assert sim.accountant.inventory == 0.0

    # Run for 2.0 seconds of virtual discrete-event time
    sim.run_for(2.0)

    assert sim.loop.current_time >= 2.0
    assert len(sim.accountant.snapshots) > 0

    metrics = sim.accountant.compute_summary_metrics()
    assert "total_mtm_pnl" in metrics
    assert "spread_capture_pnl" in metrics
    assert "inventory_risk_pnl" in metrics


def test_strategy_comparison_run():
    """Compare FixedSpread vs AvellanedaStoikov over a short run."""
    cfg = SimConfig(initial_price=50.0, tick_size=0.05)

    sim_fixed = Simulator(config=cfg, strategy=FixedSpreadStrategy(spread_ticks=4, tick_size=0.05))
    sim_fixed.run_for(1.5)

    sim_as = Simulator(config=cfg, strategy=AvellanedaStoikov(tick_size=0.05))
    sim_as.run_for(1.5)

    assert sim_fixed.loop.current_time >= 1.5
    assert sim_as.loop.current_time >= 1.5
