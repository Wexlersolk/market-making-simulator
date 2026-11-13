"""Post-fill Markout Analytics and Monte Carlo Strategy Duel Engine."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Sequence

from mmsim.latency import LatencyProfile
from mmsim.simulation import FlowRegime, MarketSimulator
from mmsim.types import Side


@dataclass
class FillRecord:
    """Single market maker fill recorded for markout analysis."""
    step: int
    side: Side
    price: float
    fair_at_fill: float


def compute_markout_curve(
    fills: Sequence[FillRecord],
    mid_history: Sequence[float],
    start_step: int = 0,
    horizons: tuple[int, ...] = (0, 1, 3, 5, 10),
) -> dict[int, float]:
    """Compute average signed post-fill markout (in $) across future horizons.

    For a BUY fill at price P: markout(h) = Mid(t + h) - P.
    For a SELL fill at price P: markout(h) = P - Mid(t + h).
    Positive markout = spread captured; declining/negative = adverse selection.
    """
    result: dict[int, float] = {}
    n_mids = len(mid_history)

    for h in horizons:
        total = 0.0
        count = 0
        for f in fills:
            idx = f.step - start_step + h
            if 0 <= idx < n_mids:
                future_mid = mid_history[idx]
                edge = (future_mid - f.price) if f.side == Side.BUY else (f.price - future_mid)
                total += edge
                count += 1
        result[h] = round(total / count, 4) if count > 0 else 0.0

    return result


@dataclass
class MonteCarloResult:
    """Aggregated statistics from batch A/B Monte Carlo simulation paths."""
    n_paths: int
    n_steps: int
    as_mtms: list[float] = field(default_factory=list)
    fixed_mtms: list[float] = field(default_factory=list)
    as_max_inv: list[float] = field(default_factory=list)
    fixed_max_inv: list[float] = field(default_factory=list)
    as_max_dd: list[float] = field(default_factory=list)
    fixed_max_dd: list[float] = field(default_factory=list)

    @staticmethod
    def _mean(vals: Sequence[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    @staticmethod
    def _std(vals: Sequence[float]) -> float:
        if len(vals) < 2:
            return 0.0
        m = sum(vals) / len(vals)
        var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
        return math.sqrt(var)

    def summary(self) -> dict[str, dict[str, float]]:
        as_mean = self._mean(self.as_mtms)
        as_std = self._std(self.as_mtms)
        fx_mean = self._mean(self.fixed_mtms)
        fx_std = self._std(self.fixed_mtms)
        return {
            "as": {
                "mean_pnl": round(as_mean, 2),
                "std_pnl": round(as_std, 2),
                "sharpe": round(as_mean / as_std, 2) if as_std > 1e-9 else 0.0,
                "avg_max_dd": round(self._mean(self.as_max_dd), 2),
                "avg_max_inv": round(self._mean(self.as_max_inv), 1),
            },
            "fixed": {
                "mean_pnl": round(fx_mean, 2),
                "std_pnl": round(fx_std, 2),
                "sharpe": round(fx_mean / fx_std, 2) if fx_std > 1e-9 else 0.0,
                "avg_max_dd": round(self._mean(self.fixed_max_dd), 2),
                "avg_max_inv": round(self._mean(self.fixed_max_inv), 1),
            },
        }


def run_monte_carlo_duel(
    n_paths: int = 20,
    n_steps: int = 200,
    flow_regime: FlowRegime = FlowRegime.NOISE,
    gamma: float = 0.1,
    sigma: float = 0.25,
    kappa: float = 1.5,
    rtt_ms: float = 2.0,
) -> MonteCarloResult:
    """Run n_paths independent A/B simulations (Avellaneda-Stoikov vs FixedSpread)."""
    res = MonteCarloResult(n_paths=n_paths, n_steps=n_steps)

    for _ in range(n_paths):
        lat = LatencyProfile(
            feed_latency_ms=rtt_ms / 2.0,
            order_latency_ms=rtt_ms / 2.0,
            jitter_std_ms=max(0.1, rtt_ms * 0.05),
        )
        sim = MarketSimulator(
            initial_price=100.0,
            tick_size=0.05,
            volatility=sigma,
            flow_regime=flow_regime,
            latency_profile=lat,
        )
        sim.mm.model.gamma = gamma
        sim.mm.model.sigma = sigma
        sim.mm.model.kappa = kappa

        as_peak = 0.0
        as_dd = 0.0
        fx_peak = 0.0
        fx_dd = 0.0
        as_inv_max = 0.0
        fx_inv_max = 0.0

        for _ in range(n_steps):
            sim.step(auto_quote=True)
            as_pnl = sim.mm.mark_to_market_pnl(sim.fair_price)
            fx_pnl = sim.baseline_mm.mark_to_market_pnl(sim.fair_price)

            as_peak = max(as_peak, as_pnl)
            as_dd = max(as_dd, as_peak - as_pnl)
            fx_peak = max(fx_peak, fx_pnl)
            fx_dd = max(fx_dd, fx_peak - fx_pnl)

            as_inv_max = max(as_inv_max, abs(sim.mm.inventory))
            fx_inv_max = max(fx_inv_max, abs(sim.baseline_mm.inventory))

        res.as_mtms.append(round(sim.mm.mark_to_market_pnl(sim.fair_price), 2))
        res.fixed_mtms.append(round(sim.baseline_mm.mark_to_market_pnl(sim.fair_price), 2))
        res.as_max_dd.append(round(as_dd, 2))
        res.fixed_max_dd.append(round(fx_dd, 2))
        res.as_max_inv.append(as_inv_max)
        res.fixed_max_inv.append(fx_inv_max)

    return res
