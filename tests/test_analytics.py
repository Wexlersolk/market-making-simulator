from mmsim.analytics import FillRecord, compute_markout_curve, run_monte_carlo_duel
from mmsim.simulation import FlowRegime
from mmsim.types import Side


def test_markout_curve_signed_edge():
    mids = [100.0, 100.10, 100.20, 99.90]
    fills = [
        FillRecord(step=0, side=Side.BUY, price=99.95, fair_at_fill=100.0),
        FillRecord(step=1, side=Side.SELL, price=100.15, fair_at_fill=100.10),
    ]
    # h=0: BUY 100.0 - 99.95 = +0.05; SELL 100.15 - 100.10 = +0.05 -> avg +0.05
    # h=1: BUY 100.10 - 99.95 = +0.15; SELL 100.15 - 100.20 = -0.05 -> avg +0.05
    # h=2: BUY 100.20 - 99.95 = +0.25; SELL 100.15 - 99.90 = +0.25 -> avg +0.25
    curve = compute_markout_curve(fills, mids, start_step=0, horizons=(0, 1, 2))
    assert curve[0] == 0.05
    assert curve[1] == 0.05
    assert curve[2] == 0.25


def test_monte_carlo_duel_runs():
    res = run_monte_carlo_duel(n_paths=4, n_steps=20, flow_regime=FlowRegime.NOISE)
    assert len(res.as_mtms) == 4
    assert len(res.fixed_mtms) == 4
    summary = res.summary()
    assert "as" in summary and "fixed" in summary
    assert "mean_pnl" in summary["as"]
    assert "avg_max_inv" in summary["fixed"]
