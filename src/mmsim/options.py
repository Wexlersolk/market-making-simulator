"""Options Pricing, Analytical Greeks, and Delta-Hedging Engine.

Why Options Market Making is Different from Equities:
1. Non-linear Payoffs: Options prices are convex functions of underlying price S (governed by Gamma).
2. The Greeks:
   - Delta (Δ): Directional sensitivity (dC/dS). Hedge ratio in underlying shares.
   - Gamma (Γ): Curvature (dΔ/dS). Measures how fast hedge ratio changes as stock moves.
   - Vega (ν): Sensitivity to implied volatility (dC/dσ).
   - Theta (Θ): Time decay per day (dC/dt). Options bleed value over time.
3. Delta-Neutral Market Making:
   - The market maker sells/buys options to earn the bid-ask spread and implied volatility premium.
   - To eliminate directional exposure, the MM continuously trades the underlying asset:
     Hedge Position = -Total Portfolio Delta.
4. Gamma Scalping:
   - Long Gamma: When stock drops, delta becomes negative -> buy stock cheap. When stock rises, sell stock high.
   - Gamma gains offset Theta decay.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from scipy.stats import norm


class OptionType(Enum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass
class Greeks:
    delta: float
    gamma: float
    vega: float      # Per 1% vol change
    theta: float     # Per calendar day
    rho: float       # Per 1% rate change


@dataclass
class OptionContract:
    option_type: OptionType
    strike: float
    expiry_years: float  # Time to maturity in years (tau)
    contract_size: int = 100


class BlackScholesEngine:
    """Analytical Black-Scholes-Merton model with full Greeks and implied volatility solver."""

    @staticmethod
    def _d1_d2(s: float, k: float, r: float, sigma: float, tau: float) -> tuple[float, float]:
        if tau <= 0 or sigma <= 0 or s <= 0 or k <= 0:
            return 0.0, 0.0
        d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * tau) / (sigma * math.sqrt(tau))
        d2 = d1 - sigma * math.sqrt(tau)
        return d1, d2

    @classmethod
    def price(
        cls,
        s: float,
        k: float,
        r: float,
        sigma: float,
        tau: float,
        option_type: OptionType = OptionType.CALL,
    ) -> float:
        """Calculate theoretical Black-Scholes option price."""
        if tau <= 1e-6:
            # At expiration payoff
            if option_type == OptionType.CALL:
                return max(0.0, s - k)
            else:
                return max(0.0, k - s)

        d1, d2 = cls._d1_d2(s, k, r, sigma, tau)

        if option_type == OptionType.CALL:
            price = s * norm.cdf(d1) - k * math.exp(-r * tau) * norm.cdf(d2)
        else:
            price = k * math.exp(-r * tau) * norm.cdf(-d2) - s * norm.cdf(-d1)

        return max(0.0, round(price, 4))

    @classmethod
    def greeks(
        cls,
        s: float,
        k: float,
        r: float,
        sigma: float,
        tau: float,
        option_type: OptionType = OptionType.CALL,
    ) -> Greeks:
        """Calculate analytical Delta, Gamma, Vega, Theta, and Rho."""
        if tau <= 1e-6 or sigma <= 1e-6:
            # Degenerate case at expiry
            in_money = (s > k) if option_type == OptionType.CALL else (s < k)
            delta = 1.0 if (option_type == OptionType.CALL and in_money) else (-1.0 if in_money else 0.0)
            return Greeks(delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)

        d1, d2 = cls._d1_d2(s, k, r, sigma, tau)
        pdf_d1 = norm.pdf(d1)
        sqrt_tau = math.sqrt(tau)

        # Gamma (identical for Call and Put)
        gamma = pdf_d1 / (s * sigma * sqrt_tau)

        # Vega (per 1 percentage point vol move, e.g. 0.01)
        vega = (s * sqrt_tau * pdf_d1) / 100.0

        if option_type == OptionType.CALL:
            delta = norm.cdf(d1)
            # Theta per calendar day (1/365)
            theta_annual = -(s * pdf_d1 * sigma) / (2.0 * sqrt_tau) - r * k * math.exp(-r * tau) * norm.cdf(d2)
            theta = theta_annual / 365.0
            rho = (k * tau * math.exp(-r * tau) * norm.cdf(d2)) / 100.0
        else:
            delta = norm.cdf(d1) - 1.0
            theta_annual = -(s * pdf_d1 * sigma) / (2.0 * sqrt_tau) + r * k * math.exp(-r * tau) * norm.cdf(-d2)
            theta = theta_annual / 365.0
            rho = (-k * tau * math.exp(-r * tau) * norm.cdf(-d2)) / 100.0

        return Greeks(
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            vega=round(vega, 4),
            theta=round(theta, 4),
            rho=round(rho, 4),
        )

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        s: float,
        k: float,
        r: float,
        tau: float,
        option_type: OptionType = OptionType.CALL,
        max_iter: int = 100,
        tol: float = 1e-5,
    ) -> Optional[float]:
        """Solve for implied volatility using Newton-Raphson method."""
        # Intrinsic value bounds check
        intrinsic = max(0.0, s - k) if option_type == OptionType.CALL else max(0.0, k - s)
        if market_price <= intrinsic:
            return None

        sigma = 0.30  # Initial guess
        for _ in range(max_iter):
            p = cls.price(s, k, r, sigma, tau, option_type)
            diff = p - market_price
            if abs(diff) < tol:
                return round(sigma, 4)

            # Vega for derivative
            d1, _ = cls._d1_d2(s, k, r, sigma, tau)
            vega = s * math.sqrt(tau) * norm.pdf(d1)
            if abs(vega) < 1e-12:
                break

            sigma -= diff / vega
            if sigma <= 0.001:
                sigma = 0.001

        return round(sigma, 4) if 0.01 <= sigma <= 5.0 else None


@dataclass
class OptionPosition:
    contract: OptionContract
    contracts_count: int  # Positive = Long, Negative = Short
    average_price: float


class OptionsPortfolio:
    """Manages an options book and tracks net Greeks and delta-hedge requirements."""

    def __init__(self, underlying_symbol: str = "XYZ", initial_cash: float = 50_000.0):
        self.underlying_symbol: str = underlying_symbol
        self.cash: float = initial_cash
        self.underlying_shares: float = 0.0  # Delta hedge inventory
        self.positions: list[OptionPosition] = []
        self.realized_pnl: float = 0.0

    def add_trade(self, contract: OptionContract, contracts_qty: int, trade_price: float):
        """Record trade execution in options contracts."""
        multiplier = contract.contract_size
        cost = contracts_qty * trade_price * multiplier
        self.cash -= cost

        # Check existing position
        for pos in self.positions:
            if (pos.contract.strike == contract.strike and
                pos.contract.option_type == contract.option_type and
                abs(pos.contract.expiry_years - contract.expiry_years) < 1e-4):
                new_qty = pos.contracts_count + contracts_qty
                if new_qty == 0:
                    self.positions.remove(pos)
                else:
                    pos.contracts_count = new_qty
                return

        self.positions.append(OptionPosition(contract, contracts_qty, trade_price))

    def net_greeks(self, s: float, r: float = 0.03, sigma: float = 0.25) -> dict[str, float]:
        """Aggregate total portfolio Greeks including underlying shares."""
        total_delta = self.underlying_shares
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0

        for pos in self.positions:
            c = pos.contract
            g = BlackScholesEngine.greeks(s, c.strike, r, sigma, c.expiry_years, c.option_type)
            factor = pos.contracts_count * c.contract_size
            total_delta += g.delta * factor
            total_gamma += g.gamma * factor
            total_vega += g.vega * factor
            total_theta += g.theta * factor

        return {
            "net_delta": round(total_delta, 2),
            "net_gamma": round(total_gamma, 4),
            "net_vega": round(total_vega, 2),
            "net_theta": round(total_theta, 2),
            "hedge_shares_needed": round(-total_delta, 0),
        }

    def execute_delta_hedge(self, s: float, r: float = 0.03, sigma: float = 0.25) -> float:
        """Buy/sell underlying shares to achieve Delta-Neutrality (Delta = 0)."""
        greeks = self.net_greeks(s, r, sigma)
        needed_shares = greeks["hedge_shares_needed"]

        if abs(needed_shares) > 0.01:
            self.underlying_shares += needed_shares
            self.cash -= needed_shares * s

        return needed_shares

    def mark_to_market(self, s: float, r: float = 0.03, sigma: float = 0.25) -> float:
        """Total portfolio value = Cash + Stock Value + Current Option Contracts Value."""
        val = self.cash + (self.underlying_shares * s)
        for pos in self.positions:
            c = pos.contract
            opt_px = BlackScholesEngine.price(s, c.strike, r, sigma, c.expiry_years, c.option_type)
            val += pos.contracts_count * opt_px * c.contract_size
        return round(val, 2)
