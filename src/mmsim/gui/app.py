"""Apex Market Making & Derivatives Station — Native PyQt6 Desktop GUI."""

import math
import sys
import random
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QPushButton, QRadioButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("qtagg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

from mmsim.gui.style import DARK_THEME_QSS
from mmsim.options import BlackScholesEngine, OptionContract, OptionType, OptionsPortfolio
from mmsim.orderbook import OrderBook
from mmsim.signals import MicrostructureSignalEngine
from mmsim.simulation import FlowRegime, MarketSimulator
from mmsim.types import Order, Side


class MainWindow(QMainWindow):
    """Institutional-grade Market Making & Derivatives Desktop Trading Station."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Market Making & Derivatives Station (Desktop)")
        self.resize(1340, 880)

        # Core Engines
        self.options_port = OptionsPortfolio(initial_cash=100_000.0)
        self.underlying_s = 100.0
        self.sim = MarketSimulator(initial_price=100.0, tick_size=0.05, flow_regime=FlowRegime.NOISE)
        self.sim.step(auto_quote=True)
        self.signal_engine = MicrostructureSignalEngine(depth_levels=5)

        # Simulation history
        self.history_steps = [0]
        self.history_mids = [100.0]
        self.history_micros = [100.0]
        self.history_bids = [99.85]
        self.history_asks = [100.15]
        self.history_spr_pnl = [0.0]
        self.history_mtm_pnl = [0.0]

        # Simulation Auto-Timer
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self.on_sim_timer_tick)
        self.is_sim_running = False

        self._build_ui()
        self.setStyleSheet(DARK_THEME_QSS)

        # Initial render
        self.update_options_ui()
        self.update_dom_ui()
        self.update_sim_ui()
        self.set_narration("System initialized. Explore Options Delta-Hedging or LOB Queue Priority below.")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # --- Top Executive Header ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 6px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(12, 6, 12, 6)

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("APEX MARKET MAKING & DERIVATIVES STATION")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #58a6ff; letter-spacing: 1px;")
        subtitle_lbl = QLabel("High-Frequency Microstructure Engine & Dynamic Delta-Neutral Hedging")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(subtitle_lbl)
        h_layout.addLayout(title_vbox)

        h_layout.addStretch()

        # Consensus metrics pill
        self.consensus_pill = QLabel("CONSENSUS: BALANCED (50%)")
        self.consensus_pill.setStyleSheet("background-color: rgba(0, 229, 255, 0.15); border: 1px solid #00e5ff; color: #00e5ff; font-weight: 700; padding: 6px 14px; border-radius: 6px;")
        h_layout.addWidget(self.consensus_pill)

        self.micro_price_lbl = QLabel("Micro-Price: $100.00 | Mid: $100.00")
        self.micro_price_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 13px; font-weight: 600; color: #f0f6fc; margin-left: 10px;")
        h_layout.addWidget(self.micro_price_lbl)

        main_layout.addWidget(header_frame)

        # --- Educational Action / Narration Banner ---
        self.narration_box = QLabel("Ready.")
        self.narration_box.setWordWrap(True)
        self.narration_box.setStyleSheet("background-color: #1c2128; border-left: 4px solid #58a6ff; border: 1px solid #30363d; color: #f0f6fc; font-size: 13px; padding: 10px 14px; border-radius: 6px; font-weight: 500;")
        main_layout.addWidget(self.narration_box)

        # --- Tab Widget ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        self.tab_options = QWidget()
        self.tab_dom = QWidget()
        self.tab_sim = QWidget()

        self.tabs.addTab(self.tab_options, "👑 Options Market Making & Delta-Hedging")
        self.tabs.addTab(self.tab_dom, "📊 Depth of Market (DOM) & Visual Queue")
        self.tabs.addTab(self.tab_sim, "⚡ HFT Equities Simulator & Avellaneda-Stoikov")

        self._build_options_tab()
        self._build_dom_tab()
        self._build_sim_tab()

    def set_narration(self, text: str, alert_type: str = "info"):
        color = "#58a6ff" if alert_type == "info" else ("#00e676" if alert_type == "success" else "#ff1744")
        self.narration_box.setText(f"💡 {text}")
        self.narration_box.setStyleSheet(f"background-color: #1c2128; border-left: 5px solid {color}; border: 1px solid #30363d; color: #f0f6fc; font-size: 13px; padding: 10px 14px; border-radius: 6px; font-weight: 500;")

    # =========================================================================
    # TAB 1: OPTIONS MARKET MAKING & DELTA HEDGING
    # =========================================================================
    def _build_options_tab(self):
        layout = QHBoxLayout(self.tab_options)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left Column: Controls & Trading
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_pane.setFixedWidth(380)

        # Contract Config Group
        grp_contract = QGroupBox("Options Contract Setup")
        cfg_layout = QGridLayout(grp_contract)

        cfg_layout.addWidget(QLabel("Option Type:"), 0, 0)
        type_hbox = QHBoxLayout()
        self.rad_call = QRadioButton("CALL")
        self.rad_put = QRadioButton("PUT")
        self.rad_call.setChecked(True)
        self.rad_call.toggled.connect(self.update_options_ui)
        type_hbox.addWidget(self.rad_call)
        type_hbox.addWidget(self.rad_put)
        cfg_layout.addLayout(type_hbox, 0, 1)

        cfg_layout.addWidget(QLabel("Strike Price ($K):"), 1, 0)
        self.spn_strike = QDoubleSpinBox()
        self.spn_strike.setRange(20.0, 300.0)
        self.spn_strike.setValue(100.0)
        self.spn_strike.setSingleStep(2.5)
        self.spn_strike.valueChanged.connect(self.update_options_ui)
        cfg_layout.addWidget(self.spn_strike, 1, 1)

        cfg_layout.addWidget(QLabel("Days to Expiration:"), 2, 0)
        self.spn_expiry = QSpinBox()
        self.spn_expiry.setRange(1, 365)
        self.spn_expiry.setValue(30)
        self.spn_expiry.valueChanged.connect(self.update_options_ui)
        cfg_layout.addWidget(self.spn_expiry, 2, 1)

        cfg_layout.addWidget(QLabel("Implied Vol (σ):"), 3, 0)
        self.spn_vol = QDoubleSpinBox()
        self.spn_vol.setRange(0.05, 2.0)
        self.spn_vol.setValue(0.25)
        self.spn_vol.setSingleStep(0.02)
        self.spn_vol.valueChanged.connect(self.update_options_ui)
        cfg_layout.addWidget(self.spn_vol, 3, 1)

        left_layout.addWidget(grp_contract)

        # Market Maker Action Group
        grp_actions = QGroupBox("Market Maker Quoting Actions")
        act_layout = QVBoxLayout(grp_actions)

        self.opt_theo_lbl = QLabel("Theoretical Price: $3.25 | Delta: +0.55")
        self.opt_theo_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e5ff; padding: 4px 0px;")
        act_layout.addWidget(self.opt_theo_lbl)

        btn_trade_hbox = QHBoxLayout()
        self.btn_sell_opt = QPushButton("Sell 5 Contracts (Ask)")
        self.btn_sell_opt.setObjectName("sellBtn")
        self.btn_sell_opt.clicked.connect(self.on_sell_options)
        self.btn_buy_opt = QPushButton("Buy 5 Contracts (Bid)")
        self.btn_buy_opt.setObjectName("buyBtn")
        self.btn_buy_opt.clicked.connect(self.on_buy_options)
        btn_trade_hbox.addWidget(self.btn_sell_opt)
        btn_trade_hbox.addWidget(self.btn_buy_opt)
        act_layout.addLayout(btn_trade_hbox)

        left_layout.addWidget(grp_actions)

        # Underlying Market Shock Simulator
        grp_shock = QGroupBox("⚡ Simulate Stock Price Moves")
        shk_layout = QGridLayout(grp_shock)

        b_dn2 = QPushButton("📉 -$2.00")
        b_dn05 = QPushButton("📉 -$0.50")
        b_up05 = QPushButton("📈 +$0.50")
        b_up2 = QPushButton("📈 +$2.00")

        b_dn2.clicked.connect(lambda: self.move_underlying(-2.0))
        b_dn05.clicked.connect(lambda: self.move_underlying(-0.5))
        b_up05.clicked.connect(lambda: self.move_underlying(0.5))
        b_up2.clicked.connect(lambda: self.move_underlying(2.0))

        shk_layout.addWidget(b_dn2, 0, 0)
        shk_layout.addWidget(b_dn05, 0, 1)
        shk_layout.addWidget(b_up05, 1, 0)
        shk_layout.addWidget(b_up2, 1, 1)

        b_theta = QPushButton("⏳ Pass 1 Day (Theta Decay Bleed)")
        b_theta.clicked.connect(self.pass_one_day)
        shk_layout.addWidget(b_theta, 2, 0, 1, 2)

        left_layout.addWidget(grp_shock)

        # Delta Hedging Command Box
        grp_hedge = QGroupBox("🛡️ Delta-Hedging Desk")
        hdg_layout = QVBoxLayout(grp_hedge)

        self.hedge_status_lbl = QLabel("Net Delta: 0.0 shares | Neutral")
        self.hedge_status_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e676;")
        hdg_layout.addWidget(self.hedge_status_lbl)

        self.btn_hedge_now = QPushButton("🛡️ EXECUTE DELTA HEDGE NOW")
        self.btn_hedge_now.setObjectName("primaryBtn")
        self.btn_hedge_now.clicked.connect(self.on_execute_delta_hedge)
        hdg_layout.addWidget(self.btn_hedge_now)

        left_layout.addWidget(grp_hedge)

        btn_reset_port = QPushButton("Reset Options Portfolio")
        btn_reset_port.clicked.connect(self.reset_options_port)
        left_layout.addWidget(btn_reset_port)
        left_layout.addStretch()

        layout.addWidget(left_pane)

        # Right Column: Graphs & Portfolio Table
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Greeks Barometer Row
        greeks_frame = QFrame()
        greeks_frame.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 8px;")
        g_layout = QHBoxLayout(greeks_frame)

        self.lbl_g_delta = QLabel("Net Delta: +0.0")
        self.lbl_g_delta.setStyleSheet("font-size: 15px; font-weight: 700; color: #58a6ff;")
        self.lbl_g_gamma = QLabel("Net Gamma: +0.0000")
        self.lbl_g_gamma.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffd700;")
        self.lbl_g_vega = QLabel("Net Vega: $0.0")
        self.lbl_g_vega.setStyleSheet("font-size: 15px; font-weight: 700; color: #a371f7;")
        self.lbl_g_theta = QLabel("Net Theta: $0.0/day")
        self.lbl_g_theta.setStyleSheet("font-size: 15px; font-weight: 700; color: #ff7b72;")

        g_layout.addWidget(self.lbl_g_delta)
        g_layout.addWidget(self.lbl_g_gamma)
        g_layout.addWidget(self.lbl_g_vega)
        g_layout.addWidget(self.lbl_g_theta)
        right_layout.addWidget(greeks_frame)

        # Matplotlib Value Profile Plot
        self.fig_options = Figure(figsize=(7, 3.2), facecolor="#161b22")
        self.canvas_options = FigureCanvasQTAgg(self.fig_options)
        right_layout.addWidget(self.canvas_options, stretch=1)

        # Positions Table
        self.table_positions = QTableWidget(0, 5)
        self.table_positions.setHorizontalHeaderLabels(["Instrument", "Position", "Current Price", "Market Value", "Net Delta"])
        self.table_positions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_positions.setFixedHeight(160)
        right_layout.addWidget(self.table_positions)

        layout.addWidget(right_pane, stretch=1)

    def update_options_ui(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        is_call = self.rad_call.isChecked()
        otype = OptionType.CALL if is_call else OptionType.PUT

        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        g = BlackScholesEngine.greeks(self.underlying_s, k, 0.04, vol, tau, otype)

        self.opt_theo_lbl.setText(f"Theoretical Price: ${theo:.2f} | Δ: {g.delta:+.4f} | Γ: {g.gamma:.4f}")

        # Update Net Greeks
        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, vol)
        nd = net_g["net_delta"]
        needed = net_g["hedge_shares_needed"]

        self.lbl_g_delta.setText(f"Net Delta: {nd:+.1f} shs")
        self.lbl_g_gamma.setText(f"Net Gamma: {net_g['net_gamma']:+.4f}")
        self.lbl_g_vega.setText(f"Net Vega: ${net_g['net_vega']:+.1f}")
        self.lbl_g_theta.setText(f"Net Theta: ${net_g['net_theta']:+.1f}/day")

        if abs(needed) > 0.0:
            self.hedge_status_lbl.setText(f"⚠️ Net Delta: {nd:+.1f} | Action: {'BUY' if needed>0 else 'SELL'} {abs(needed):.0f} shares")
            self.hedge_status_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #ff7b72;")
        else:
            self.hedge_status_lbl.setText("✅ Portfolio is Delta-Neutral (Delta ≈ 0.0)")
            self.hedge_status_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e676;")

        # Update Matplotlib Curve
        self.fig_options.clear()
        ax = self.fig_options.add_subplot(111)
        ax.set_facecolor("#0d1117")

        s_range = np.linspace(max(10.0, k - 30.0), k + 30.0, 100)
        now_prices = [BlackScholesEngine.price(s_i, k, 0.04, vol, tau, otype) for s_i in s_range]
        exp_prices = [BlackScholesEngine.price(s_i, k, 0.04, vol, 0.0, otype) for s_i in s_range]

        ax.plot(s_range, exp_prices, "--", color="#6e7681", label="Expiry Payoff", linewidth=1.5)
        ax.plot(s_range, now_prices, "-", color="#00e5ff", label=f"Today ({self.spn_expiry.value()}d Expiry)", linewidth=2.5)

        # Mark current point
        ax.plot([self.underlying_s], [theo], "o", color="#ffea00", markersize=9, label=f"Current Stock (${self.underlying_s:.2f})")
        ax.axvline(self.underlying_s, color="#ffea00", linestyle=":", alpha=0.4)
        ax.axvline(k, color="#8b949e", linestyle="--", alpha=0.3)

        ax.set_title(f"{'CALL' if is_call else 'PUT'} Value Profile (Strike ${k:.2f}, IV {vol*100:.0f}%)", color="#f0f6fc", fontsize=11, fontweight="bold")
        ax.set_xlabel("Underlying Stock Price ($)", color="#8b949e", fontsize=10)
        ax.set_ylabel("Option Price ($)", color="#8b949e", fontsize=10)
        ax.tick_params(colors="#8b949e", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.grid(True, color="#21262d", linestyle="--", alpha=0.7)
        ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=9)
        self.fig_options.tight_layout()
        self.canvas_options.draw()

        # Update Positions Table
        self.table_positions.setRowCount(0)
        # 1. Underlying
        r_idx = self.table_positions.rowCount()
        self.table_positions.insertRow(r_idx)
        self.table_positions.setItem(r_idx, 0, QTableWidgetItem(f"Underlying Stock ({self.options_port.underlying_symbol})"))
        self.table_positions.setItem(r_idx, 1, QTableWidgetItem(f"{self.options_port.underlying_shares:+.0f} shares"))
        self.table_positions.setItem(r_idx, 2, QTableWidgetItem(f"${self.underlying_s:.2f}"))
        self.table_positions.setItem(r_idx, 3, QTableWidgetItem(f"${self.options_port.underlying_shares * self.underlying_s:,.2f}"))
        self.table_positions.setItem(r_idx, 4, QTableWidgetItem(f"{self.options_port.underlying_shares:+.1f}"))

        # 2. Options
        for pos in self.options_port.positions:
            c = pos.contract
            cur_p = BlackScholesEngine.price(self.underlying_s, c.strike, 0.04, vol, c.expiry_years, c.option_type)
            cg = BlackScholesEngine.greeks(self.underlying_s, c.strike, 0.04, vol, c.expiry_years, c.option_type)
            r_idx = self.table_positions.rowCount()
            self.table_positions.insertRow(r_idx)
            self.table_positions.setItem(r_idx, 0, QTableWidgetItem(f"{c.option_type.value} ${c.strike:.1f} ({int(c.expiry_years*365)}d)"))
            self.table_positions.setItem(r_idx, 1, QTableWidgetItem(f"{pos.contracts_count:+} contracts"))
            self.table_positions.setItem(r_idx, 2, QTableWidgetItem(f"${cur_p:.2f}"))
            self.table_positions.setItem(r_idx, 3, QTableWidgetItem(f"${pos.contracts_count * cur_p * c.contract_size:,.2f}"))
            self.table_positions.setItem(r_idx, 4, QTableWidgetItem(f"{cg.delta * pos.contracts_count * c.contract_size:+.1f}"))

    def on_sell_options(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        otype = OptionType.CALL if self.rad_call.isChecked() else OptionType.PUT
        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        spread_px = round(theo + 0.15, 2)

        c = OptionContract(otype, k, tau, 100)
        self.options_port.add_trade(c, contracts_qty=-5, trade_price=spread_px)
        self.update_options_ui()

        g = BlackScholesEngine.greeks(self.underlying_s, k, 0.04, vol, tau, otype)
        delta_impact = -5 * 100 * g.delta
        self.set_narration(
            f"⚡ SOLD 5 {otype.value}s @ ${spread_px:.2f} (collected ${spread_px*500:,.2f} cash)! "
            f"Your Net Delta jumped by {delta_impact:+.0f} shares. You now have directional risk. "
            f"Click [EXECUTE DELTA HEDGE] to neutralize.",
            "success",
        )

    def on_buy_options(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        otype = OptionType.CALL if self.rad_call.isChecked() else OptionType.PUT
        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        spread_px = round(max(0.01, theo - 0.15), 2)

        c = OptionContract(otype, k, tau, 100)
        self.options_port.add_trade(c, contracts_qty=5, trade_price=spread_px)
        self.update_options_ui()

        g = BlackScholesEngine.greeks(self.underlying_s, k, 0.04, vol, tau, otype)
        delta_impact = 5 * 100 * g.delta
        self.set_narration(
            f"🛒 BOUGHT 5 {otype.value}s @ ${spread_px:.2f} (cost ${spread_px*500:,.2f}). "
            f"Delta shifted by {delta_impact:+.0f} shares. Re-hedge to lock in volatility edge.",
            "info",
        )

    def move_underlying(self, delta_s: float):
        old_s = self.underlying_s
        self.underlying_s = max(10.0, round(self.underlying_s + delta_s, 2))
        self.update_options_ui()

        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, self.spn_vol.value())
        self.set_narration(
            f"📈 Underlying stock moved from ${old_s:.2f} to ${self.underlying_s:.2f} (ΔS = {delta_s:+.2f}). "
            f"Notice how option value curved (Gamma effect) and Net Delta changed to {net_g['net_delta']:+.1f}. "
            f"Re-hedging now captures Gamma Scalping profits!",
            "info",
        )

    def pass_one_day(self):
        cur_days = self.spn_expiry.value()
        if cur_days > 1:
            self.spn_expiry.setValue(cur_days - 1)
            self.update_options_ui()
            net_g = self.options_port.net_greeks(self.underlying_s, 0.04, self.spn_vol.value())
            self.set_narration(
                f"⏳ Advanced 1 Day. Time to expiry is now {cur_days-1} days. "
                f"Theta decay bled approximately ${abs(net_g['net_theta']):.2f} from the option's extrinsic value.",
                "info",
            )

    def on_execute_delta_hedge(self):
        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, self.spn_vol.value())
        shares_needed = net_g["hedge_shares_needed"]
        if abs(shares_needed) > 0.0:
            traded = self.options_port.execute_delta_hedge(self.underlying_s, 0.04, self.spn_vol.value())
            self.update_options_ui()
            action = "BOUGHT" if traded > 0 else "SOLD"
            self.set_narration(
                f"🛡️ DELTA HEDGE COMPLETE: {action} {abs(traded):.0f} shares of stock at ${self.underlying_s:.2f}. "
                f"Net Delta is now 0.0! Your portfolio is immunized against immediate directional market moves.",
                "success",
            )
        else:
            self.set_narration("Portfolio is already Delta-Neutral (Delta ≈ 0.0). No hedge required.", "info")

    def reset_options_port(self):
        self.options_port = OptionsPortfolio(initial_cash=100_000.0)
        self.underlying_s = 100.0
        self.update_options_ui()
        self.set_narration("Options desk reset to clean initial state.", "info")

    # =========================================================================
    # TAB 2: DEPTH OF MARKET (DOM) & QUEUE PRIORITY
    # =========================================================================
    def _build_dom_tab(self):
        layout = QHBoxLayout(self.tab_dom)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left: DOM Ladder Table
        dom_group = QGroupBox("Depth of Market (DOM) Price Ladder")
        dom_layout = QVBoxLayout(dom_group)

        self.table_dom = QTableWidget(0, 3)
        self.table_dom.setHorizontalHeaderLabels(["Bid Depth", "Price ($)", "Ask Depth"])
        self.table_dom.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        dom_layout.addWidget(self.table_dom)

        btn_resample = QPushButton("Reseed Order Book Depth")
        btn_resample.clicked.connect(self.on_reseed_book)
        dom_layout.addWidget(btn_resample)

        layout.addWidget(dom_group, stretch=1)

        # Right: Visual Queue & Market Sweeper
        queue_group = QGroupBox("FIFO Queue Priority & Market Order Sweeper")
        q_layout = QVBoxLayout(queue_group)

        q_info = QLabel(
            "In exchange matching engines, orders at the SAME price wait in a strict FIFO queue.\n"
            "Your limit order only executes after all orders placed ahead of you have been completely filled."
        )
        q_info.setWordWrap(True)
        q_info.setStyleSheet("color: #8b949e; font-size: 12px; margin-bottom: 8px;")
        q_layout.addWidget(q_info)

        # Queue Visualizer Canvas
        self.fig_queue = Figure(figsize=(5, 3.0), facecolor="#161b22")
        self.canvas_queue = FigureCanvasQTAgg(self.fig_queue)
        q_layout.addWidget(self.canvas_queue, stretch=1)

        # Market Sweeper Controls
        sweep_box = QFrame()
        sweep_box.setStyleSheet("background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px;")
        sw_layout = QHBoxLayout(sweep_box)

        sw_layout.addWidget(QLabel("Market Sell Size:"))
        self.spn_sweep_qty = QDoubleSpinBox()
        self.spn_sweep_qty.setRange(1.0, 50.0)
        self.spn_sweep_qty.setValue(15.0)
        sw_layout.addWidget(self.spn_sweep_qty)

        btn_sweep = QPushButton("🔥 FIRE MARKET SELL ORDER")
        btn_sweep.setObjectName("sellBtn")
        btn_sweep.clicked.connect(self.on_sweep_market_order)
        sw_layout.addWidget(btn_sweep)

        q_layout.addWidget(sweep_box)
        layout.addWidget(queue_group, stretch=1)

    def update_dom_ui(self):
        book = self.sim.book
        bid_d, ask_d = book.get_depth(max_levels=8)
        b_map = {p: v for p, v in bid_d}
        a_map = {p: v for p, v in ask_d}
        prices = sorted(set(list(b_map.keys()) + list(a_map.keys())), reverse=True)

        self.table_dom.setRowCount(0)
        for p in prices:
            r = self.table_dom.rowCount()
            self.table_dom.insertRow(r)

            b_vol = b_map.get(p, 0.0)
            a_vol = a_map.get(p, 0.0)

            # Check MM tags
            orders = book.get_level_orders(Side.BUY if b_vol > 0 else Side.SELL, p)
            is_mm = any(o.is_mm for o in orders)
            tag = " ★ [MM]" if is_mm else ""

            b_item = QTableWidgetItem(f"{b_vol:.0f}{tag}" if b_vol > 0 else "")
            if b_vol > 0:
                b_item.setForeground(QColor("#00e676"))
                b_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            p_item = QTableWidgetItem(f"${p:.2f}")
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            p_item.setFont(QFont("JetBrains Mono", 11, QFont.Weight.Bold))

            a_item = QTableWidgetItem(f"{a_vol:.0f}{tag}" if a_vol > 0 else "")
            if a_vol > 0:
                a_item.setForeground(QColor("#ff1744"))
                a_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.table_dom.setItem(r, 0, b_item)
            self.table_dom.setItem(r, 1, p_item)
            self.table_dom.setItem(r, 2, a_item)

        # Update Queue Canvas at Best Bid
        self.fig_queue.clear()
        ax = self.fig_queue.add_subplot(111)
        ax.set_facecolor("#0d1117")

        bb = book.best_bid()
        if bb is not None:
            q_orders = book.get_level_orders(Side.BUY, bb)
            if q_orders:
                # Draw queue blocks
                names = [("★ YOU (MM)" if o.is_mm else o.trader_id) for o in q_orders]
                vols = [o.quantity for o in q_orders]
                colors = ["#1f6feb" if o.is_mm else "#30363d" for o in q_orders]

                y_pos = np.arange(len(names))
                ax.barh(y_pos, vols, color=colors, edgecolor="#58a6ff", height=0.6)
                ax.set_yticks(y_pos)
                ax.set_yticklabels([f"#{i+1}: {n}" for i, n in enumerate(names)], color="#c9d1d9", fontsize=10)
                ax.invert_yaxis()  # Head of queue at top

                for i, v in enumerate(vols):
                    ax.text(v + 0.3, i, f"{v:.0f} qty", va="center", color="#f0f6fc", fontsize=9, fontweight="bold")

                ax.set_title(f"FIFO Queue at Best Bid (${bb:.2f}) — Top is Head of Line", color="#f0f6fc", fontsize=11, fontweight="bold")
                ax.set_xlabel("Order Size (Units)", color="#8b949e", fontsize=10)
            else:
                ax.text(0.5, 0.5, "No orders at Best Bid", ha="center", color="#8b949e")
        else:
            ax.text(0.5, 0.5, "Empty Book", ha="center", color="#8b949e")

        ax.tick_params(colors="#8b949e")
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.grid(True, color="#21262d", linestyle="--", alpha=0.5, axis="x")
        self.fig_queue.tight_layout()
        self.canvas_queue.draw()

        # Update Header Consensus Barometer
        cs = self.signal_engine.evaluate_consensus(book)
        if cs:
            self.micro_price_lbl.setText(f"Micro-Price: ${cs.micro_price:.4f} | Mid: ${cs.mid_price:.2f} | OBI: {cs.order_book_imbalance:+.2f}")
            c_text = f"CONSENSUS: {cs.regime.value} ({cs.confidence_pct:.0f}%)"
            self.consensus_pill.setText(c_text)
            c_color = "#00e676" if "BUY" in cs.regime.value else ("#ff1744" if "SELL" in cs.regime.value else "#00e5ff")
            self.consensus_pill.setStyleSheet(f"background-color: rgba(255,255,255,0.05); border: 1px solid {c_color}; color: {c_color}; font-weight: 700; padding: 6px 14px; border-radius: 6px;")

    def on_sweep_market_order(self):
        qty = self.spn_sweep_qty.value()
        trades, unfilled = self.sim.book.execute_market_order("AggressiveTaker", Side.SELL, qty, 0.0)
        self.update_dom_ui()

        # Check if MM was filled
        mm_filled = sum(t.quantity for t in trades if t.maker_trader_id == self.sim.mm.trader_id)
        if mm_filled > 0:
            self.set_narration(
                f"🎯 MARKET ORDER SWEEP: Taker sold {qty:.0f} units! "
                f"Queue orders ahead filled first, then YOUR MM quote got filled for {mm_filled:.0f} units! "
                f"You bought low to earn spread.",
                "success",
            )
        else:
            self.set_narration(
                f"🛡️ QUEUE PRIORITY IN ACTION: Taker sold {qty:.0f} units. "
                f"All volume was eaten by orders ahead of you in line. Your resting quote remained untouched!",
                "info",
            )

    def on_reseed_book(self):
        self.sim = MarketSimulator(initial_price=100.0, tick_size=0.05)
        self.sim.step(auto_quote=True)
        self.update_dom_ui()
        self.set_narration("Order book reseeded with fresh two-sided background liquidity.", "info")

    # =========================================================================
    # TAB 3: EQUITIES HFT SIMULATOR & AVELLANEDA-STOIKOV
    # =========================================================================
    def _build_sim_tab(self):
        layout = QHBoxLayout(self.tab_sim)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left: Controls
        left_ctrl = QWidget()
        l_layout = QVBoxLayout(left_ctrl)
        l_layout.setContentsMargins(0, 0, 0, 0)
        left_ctrl.setFixedWidth(340)

        grp_sim_ctrl = QGroupBox("Simulation Loop Controls")
        sc_layout = QVBoxLayout(grp_sim_ctrl)

        # Flow Regime Selector
        sc_layout.addWidget(QLabel("Order Flow Regime:"))
        self.cmb_regime = QComboBox()
        self.cmb_regime.addItem(FlowRegime.NOISE.value, FlowRegime.NOISE)
        self.cmb_regime.addItem(FlowRegime.MOMENTUM.value, FlowRegime.MOMENTUM)
        self.cmb_regime.addItem(FlowRegime.TOXIC.value, FlowRegime.TOXIC)
        self.cmb_regime.currentIndexChanged.connect(self.on_regime_changed)
        sc_layout.addWidget(self.cmb_regime)

        # Play / Pause / Step
        self.btn_play = QPushButton("▶ START AUTO-SIMULATION")
        self.btn_play.setObjectName("primaryBtn")
        self.btn_play.clicked.connect(self.toggle_simulation)
        sc_layout.addWidget(self.btn_play)

        btn_step1 = QPushButton("Step +1 Tick")
        btn_step1.clicked.connect(lambda: self.step_sim_ticks(1))
        btn_step10 = QPushButton("Step +10 Ticks")
        btn_step10.clicked.connect(lambda: self.step_sim_ticks(10))

        h_step = QHBoxLayout()
        h_step.addWidget(btn_step1)
        h_step.addWidget(btn_step10)
        sc_layout.addLayout(h_step)

        btn_reset_sim = QPushButton("Reset Simulator")
        btn_reset_sim.clicked.connect(self.reset_sim)
        sc_layout.addWidget(btn_reset_sim)

        l_layout.addWidget(grp_sim_ctrl)

        # Telemetry Card
        grp_telem = QGroupBox("MM PnL & Risk Attribution")
        t_layout = QVBoxLayout(grp_telem)

        self.lbl_t_inv = QLabel("Inventory (q): 0 units")
        self.lbl_t_inv.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 14px; font-weight: 700; color: #ffd700;")
        self.lbl_t_spr = QLabel("Spread PnL: $0.00")
        self.lbl_t_spr.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 14px; font-weight: 700; color: #00e676;")
        self.lbl_t_mtm = QLabel("Total MTM PnL: $0.00")
        self.lbl_t_mtm.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 14px; font-weight: 700; color: #58a6ff;")

        t_layout.addWidget(self.lbl_t_inv)
        t_layout.addWidget(self.lbl_t_spr)
        t_layout.addWidget(self.lbl_t_mtm)
        l_layout.addWidget(grp_telem)

        # Execution Tape
        grp_tape = QGroupBox("Live Execution Tape")
        tp_layout = QVBoxLayout(grp_tape)
        self.txt_tape = QTextEdit()
        self.txt_tape.setReadOnly(True)
        self.txt_tape.setStyleSheet("background-color: #0d1117; color: #8b949e; font-family: 'JetBrains Mono'; font-size: 11px;")
        tp_layout.addWidget(self.txt_tape)
        l_layout.addWidget(grp_tape)
        l_layout.addStretch()

        layout.addWidget(left_ctrl)

        # Right: Live Charts
        right_charts = QWidget()
        r_layout = QVBoxLayout(right_charts)
        r_layout.setContentsMargins(0, 0, 0, 0)

        self.fig_sim = Figure(figsize=(7, 6.0), facecolor="#161b22")
        self.canvas_sim = FigureCanvasQTAgg(self.fig_sim)
        r_layout.addWidget(self.canvas_sim)

        layout.addWidget(right_charts, stretch=1)

    def on_regime_changed(self):
        reg = self.cmb_regime.currentData()
        self.sim.flow_regime = reg
        self.set_narration(f"Order flow switched to {reg.value}.", "info")

    def toggle_simulation(self):
        if self.is_sim_running:
            self.sim_timer.stop()
            self.is_sim_running = False
            self.btn_play.setText("▶ START AUTO-SIMULATION")
            self.btn_play.setStyleSheet("")
            self.set_narration("Simulation paused.", "info")
        else:
            self.sim_timer.start(300)  # Tick every 300ms
            self.is_sim_running = True
            self.btn_play.setText("⏸ PAUSE SIMULATION")
            self.btn_play.setStyleSheet("background-color: #ff7b72; color: white;")
            self.set_narration("Live HFT simulation running continuously at 300ms/tick...", "info")

    def on_sim_timer_tick(self):
        self.step_sim_ticks(1)

    def step_sim_ticks(self, count: int):
        for _ in range(count):
            events = self.sim.step(auto_quote=True)
            self.history_steps.append(self.sim.step_count)
            self.history_mids.append(self.sim.fair_price)
            micro = self.signal_engine.compute_micro_price(self.sim.book) or self.sim.fair_price
            self.history_micros.append(micro)
            bb = self.sim.book.best_bid() or self.sim.fair_price
            ba = self.sim.book.best_ask() or self.sim.fair_price
            self.history_bids.append(bb)
            self.history_asks.append(ba)
            self.history_spr_pnl.append(self.sim.mm.spread_pnl)
            self.history_mtm_pnl.append(self.sim.mm.mark_to_market_pnl(self.sim.fair_price))

            # Tape logging
            for ev in events:
                if "MM FILLED" in ev.description:
                    self.txt_tape.append(f"<span style='color:#00e676;'>{ev.description}</span>")
                    self.set_narration(ev.description, "success")
                elif "SHOCK" in ev.description:
                    self.txt_tape.append(f"<span style='color:#ff1744; font-weight:bold;'>{ev.description}</span>")
                    self.set_narration(ev.description, "alert")
                else:
                    self.txt_tape.append(f"• {ev.description}")

        self.update_sim_ui()
        self.update_dom_ui()

    def update_sim_ui(self):
        # Update metrics
        inv = self.sim.mm.inventory
        spr = self.sim.mm.spread_pnl
        tot = self.sim.mm.mark_to_market_pnl(self.sim.fair_price)

        self.lbl_t_inv.setText(f"Inventory (q): {inv:+.0f} units")
        self.lbl_t_spr.setText(f"Spread PnL: ${spr:,.2f}")
        self.lbl_t_mtm.setText(f"Total MTM PnL: ${tot:,.2f}")

        # Update Plots (2 subplots: Price/Quotes on top, PnL Attribution on bottom)
        self.fig_sim.clear()
        ax1 = self.fig_sim.add_subplot(211)
        ax2 = self.fig_sim.add_subplot(212, sharex=ax1)

        ax1.set_facecolor("#0d1117")
        ax2.set_facecolor("#0d1117")

        steps = self.history_steps[-60:]
        mids = self.history_mids[-60:]
        micros = self.history_micros[-60:]
        bids = self.history_bids[-60:]
        asks = self.history_asks[-60:]
        spr_pnls = self.history_spr_pnl[-60:]
        mtm_pnls = self.history_mtm_pnl[-60:]

        # Price / Micro-Price / Quotes
        ax1.plot(steps, mids, "-", color="#ffd700", label="Mid Price", linewidth=2)
        ax1.plot(steps, micros, ":", color="#00e5ff", label="Stoikov Micro-Price", linewidth=1.5)
        ax1.plot(steps, bids, "--", color="#00e676", label="MM Bid", alpha=0.8)
        ax1.plot(steps, asks, "--", color="#ff1744", label="MM Ask", alpha=0.8)
        ax1.set_title("Mid Price vs Micro-Price & MM Quoting Envelope", color="#f0f6fc", fontsize=11, fontweight="bold")
        ax1.set_ylabel("Price ($)", color="#8b949e", fontsize=10)
        ax1.tick_params(colors="#8b949e")
        for spine in ax1.spines.values():
            spine.set_color("#30363d")
        ax1.grid(True, color="#21262d", linestyle="--", alpha=0.5)
        ax1.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=8, loc="upper left")

        # PnL Attribution (Spread vs MTM)
        ax2.plot(steps, spr_pnls, "-", color="#00e676", label="Spread Capture PnL (Passive Edge)", linewidth=2)
        ax2.plot(steps, mtm_pnls, "-", color="#58a6ff", label="Total MTM PnL (Includes Inventory Risk)", linewidth=2)
        ax2.axhline(0, color="#8b949e", linestyle="--", alpha=0.5)
        ax2.set_title("PnL Attribution: Spread Capture vs Directional Beta", color="#f0f6fc", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Simulation Step", color="#8b949e", fontsize=10)
        ax2.set_ylabel("PnL ($)", color="#8b949e", fontsize=10)
        ax2.tick_params(colors="#8b949e")
        for spine in ax2.spines.values():
            spine.set_color("#30363d")
        ax2.grid(True, color="#21262d", linestyle="--", alpha=0.5)
        ax2.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=8, loc="upper left")

        self.fig_sim.tight_layout()
        self.canvas_sim.draw()

    def reset_sim(self):
        if self.is_sim_running:
            self.toggle_simulation()
        self.sim = MarketSimulator(initial_price=100.0, tick_size=0.05)
        self.sim.step(auto_quote=True)
        self.history_steps = [0]
        self.history_mids = [100.0]
        self.history_micros = [100.0]
        self.history_bids = [99.85]
        self.history_asks = [100.15]
        self.history_spr_pnl = [0.0]
        self.history_mtm_pnl = [0.0]
        self.txt_tape.clear()
        self.update_sim_ui()
        self.update_dom_ui()
        self.set_narration("Simulator reset.", "info")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
