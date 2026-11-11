import math
import pytest
from mmsim.options import BlackScholesEngine, OptionContract, OptionType, OptionsPortfolio


def test_black_scholes_pricing_and_put_call_parity():
    s = 100.0
    k = 100.0
    r = 0.05
    sigma = 0.20
    tau = 1.0

    call_px = BlackScholesEngine.price(s, k, r, sigma, tau, OptionType.CALL)
    put_px = BlackScholesEngine.price(s, k, r, sigma, tau, OptionType.PUT)

    # Standard ATM Call ~ 10.45
    assert math.isclose(call_px, 10.4506, rel_tol=1e-3)

    # Put-Call Parity: C - P = S - K * exp(-r * tau)
    lhs = call_px - put_px
    rhs = s - k * math.exp(-r * tau)
    assert math.isclose(lhs, rhs, abs_tol=1e-3)


def test_analytical_greeks():
    s = 100.0
    k = 100.0
    r = 0.05
    sigma = 0.20
    tau = 1.0

    g_call = BlackScholesEngine.greeks(s, k, r, sigma, tau, OptionType.CALL)
    g_put = BlackScholesEngine.greeks(s, k, r, sigma, tau, OptionType.PUT)

    # ATM Call Delta ~ 0.637, Put Delta = Call Delta - 1 ~ -0.363
    assert 0.50 < g_call.delta < 0.70
    assert math.isclose(g_call.delta - 1.0, g_put.delta, abs_tol=1e-3)

    # Gamma and Vega are identical and positive
    assert g_call.gamma > 0
    assert g_call.gamma == g_put.gamma
    assert g_call.vega > 0
    assert g_call.vega == g_put.vega

    # Theta is negative (time decay)
    assert g_call.theta < 0
    assert g_put.theta < 0


def test_implied_volatility_solver():
    s, k, r, tau = 100.0, 100.0, 0.05, 1.0
    true_vol = 0.35
    market_price = BlackScholesEngine.price(s, k, r, true_vol, tau, OptionType.CALL)

    solved_iv = BlackScholesEngine.implied_volatility(market_price, s, k, r, tau, OptionType.CALL)
    assert solved_iv is not None
    assert math.isclose(solved_iv, true_vol, abs_tol=1e-3)


def test_delta_hedging_portfolio():
    port = OptionsPortfolio(initial_cash=100_000.0)
    contract = OptionContract(OptionType.CALL, strike=100.0, expiry_years=0.5, contract_size=100)

    # Market maker sells 5 Call contracts (500 options)
    # Each call has delta ~0.55 -> total delta sold ~ -275
    port.add_trade(contract, contracts_qty=-5, trade_price=6.0)

    g1 = port.net_greeks(s=100.0, r=0.03, sigma=0.25)
    assert g1["net_delta"] < 0  # Short calls -> negative delta
    assert g1["hedge_shares_needed"] > 0  # Must buy stock to hedge

    # Execute Delta Hedge
    shares_bought = port.execute_delta_hedge(s=100.0, r=0.03, sigma=0.25)
    assert shares_bought > 0

    # Net delta must now be approximately 0
    g2 = port.net_greeks(s=100.0, r=0.03, sigma=0.25)
    assert abs(g2["net_delta"]) < 1.0
