"""Apex Market Making & Derivatives Station — Native PyQt6 Desktop GUI."""

import sys
import uuid
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow, QPushButton, QRadioButton,
    QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("qtagg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

from mmsim.analytics import FillRecord, compute_markout_curve, run_monte_carlo_duel
from mmsim.gui.style import DARK_THEME_QSS
from mmsim.options import BlackScholesEngine, OptionContract, OptionType, OptionsPortfolio
from mmsim.signals import MicrostructureSignalEngine
from mmsim.simulation import FlowRegime, MarketSimulator
from mmsim.types import Order, Side


def _make_kpi_card(title: str, initial_val: str, color: str = "#f0f6fc") -> tuple[QFrame, QLabel, QLabel]:
    """Create a clean institutional KPI card with title, primary value, and subtitle."""
    card = QFrame()
    card.setObjectName("kpiCard")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)

    lbl_t = QLabel(title)
    lbl_t.setObjectName("kpiTitle")

    lbl_v = QLabel(initial_val)
    lbl_v.setObjectName("kpiValue")
    lbl_v.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 17px; font-weight: 700; color: {color};")

    lbl_s = QLabel("")
    lbl_s.setObjectName("kpiSub")

    lay.addWidget(lbl_t)
    lay.addWidget(lbl_v)
    lay.addWidget(lbl_s)
    return card, lbl_v, lbl_s


class MainWindow(QMainWindow):
    """Institutional-grade Market Making & Derivatives Desktop Trading Station."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Apex Market Making & Microstructure Lab")

        # Almost fullscreen: 96% x 95% of primary screen
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            w = int(geo.width() * 0.96)
            h = int(geo.height() * 0.95)
            self.resize(w, h)
            self.move(geo.left() + (geo.width() - w) // 2, geo.top() + (geo.height() - h) // 2)
        else:
            self.resize(1680, 1000)

        # Core Engines
        self.initial_options_cash = 100_000.0
        self.options_port = OptionsPortfolio(initial_cash=self.initial_options_cash)
        self.underlying_s = 100.0

        self.sim = MarketSimulator(initial_price=100.0, tick_size=0.05, flow_regime=FlowRegime.NOISE)
        self.sim.step(auto_quote=True)
        self.signal_engine = MicrostructureSignalEngine(depth_levels=5)

        # Manual DOM orders placed by user click: {(side, price): order_id}
        self.manual_dom_orders: dict[tuple[Side, float], str] = {}

        # Simulation history
        self.history_steps: list[int] = []
        self.history_mids: list[float] = []
        self.history_res: list[float] = []
        self.history_micros: list[float] = []
        self.history_bids: list[float] = []
        self.history_asks: list[float] = []
        self.history_inv: list[float] = []
        self.history_spr_pnl: list[float] = []
        self.history_mtm_pnl: list[float] = []
        self.history_bl_inv: list[float] = []
        self.history_bl_mtm_pnl: list[float] = []
        self.buy_fills: list[tuple[int, float]] = []    # (step, price)
        self.sell_fills: list[tuple[int, float]] = []   # (step, price)
        self.stale_fills: list[tuple[int, float]] = []  # (step, price)
        self.fill_records: list[FillRecord] = []
        self.last_mc_result = None
        self._init_sim_history()

        # Simulation Auto-Timer
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self.on_sim_timer_tick)
        self.is_sim_running = False

        self._build_ui()
        self.setStyleSheet(DARK_THEME_QSS)

        # Initial render
        self.update_sim_ui()
        self.update_dom_ui()
        self.update_options_ui()
        self.update_analytics_ui()
        self.set_narration(
            "Ready. Step or start the HFT Simulator to compare Avellaneda-Stoikov vs FixedSpread and test Latency sniping.",
            "info",
        )

    def _init_sim_history(self):
        bid, ask, res_p = self.sim.mm.compute_quotes(self.sim.fair_price)
        micro = self.signal_engine.compute_micro_price(self.sim.book) or self.sim.fair_price
        self.history_steps = [self.sim.step_count]
        self.history_mids = [self.sim.fair_price]
        self.history_res = [res_p]
        self.history_micros = [micro]
        self.history_bids = [bid]
        self.history_asks = [ask]
        self.history_inv = [self.sim.mm.inventory]
        self.history_spr_pnl = [self.sim.mm.spread_pnl]
        self.history_mtm_pnl = [self.sim.mm.mark_to_market_pnl(self.sim.fair_price)]
        self.history_bl_inv = [self.sim.baseline_mm.inventory]
        self.history_bl_mtm_pnl = [self.sim.baseline_mm.mark_to_market_pnl(self.sim.fair_price)]
        self.buy_fills = []
        self.sell_fills = []
        self.stale_fills = []
        self.fill_records = []

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # --- Top Executive Header ---
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(14, 8, 14, 8)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        title_lbl = QLabel("APEX MARKET MAKING & MICROSTRUCTURE LAB")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #58a6ff; letter-spacing: 0.8px;")
        subtitle_lbl = QLabel("Avellaneda-Stoikov Inventory Skew  |  FIFO Order Book Queue  |  Options Delta-Hedging")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(subtitle_lbl)
        h_layout.addLayout(title_vbox)

        h_layout.addStretch()

        self.consensus_pill = QLabel("CONSENSUS: BALANCED (50%)")
        self.consensus_pill.setStyleSheet(
            "background-color: rgba(0, 229, 255, 0.12); border: 1px solid #00e5ff; "
            "color: #00e5ff; font-weight: 700; font-size: 11px; padding: 5px 12px; border-radius: 6px;"
        )
        h_layout.addWidget(self.consensus_pill)

        self.micro_price_lbl = QLabel("Micro: $100.0000 | Mid: $100.00 | OBI: +0.00")
        self.micro_price_lbl.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; color: #f0f6fc; margin-left: 10px;"
        )
        h_layout.addWidget(self.micro_price_lbl)

        main_layout.addWidget(header_frame)

        # --- Live Narration Banner ---
        self.narration_box = QLabel("Ready.")
        self.narration_box.setWordWrap(True)
        main_layout.addWidget(self.narration_box)

        # --- Tab Widget (HFT Simulator first for immediate MM intuition) ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        self.tab_sim = QWidget()
        self.tab_dom = QWidget()
        self.tab_options = QWidget()
        self.tab_analytics = QWidget()

        self.tabs.addTab(self.tab_sim, "HFT Simulator & Avellaneda-Stoikov")
        self.tabs.addTab(self.tab_dom, "Depth of Market (DOM) & Queue")
        self.tabs.addTab(self.tab_options, "Options & Delta-Hedging")
        self.tabs.addTab(self.tab_analytics, "Analytics: Markout & Monte Carlo")

        self._build_sim_tab()
        self._build_dom_tab()
        self._build_options_tab()
        self._build_analytics_tab()

    def set_narration(self, text: str, alert_type: str = "info"):
        color = "#58a6ff" if alert_type == "info" else ("#00e676" if alert_type == "success" else "#ff5252")
        self.narration_box.setText(text)
        self.narration_box.setStyleSheet(
            f"background-color: #131820; border: 1px solid #262c36; border-left: 4px solid {color}; "
            "color: #e6edf3; font-size: 12px; padding: 8px 12px; border-radius: 6px; font-weight: 500;"
        )

    # =========================================================================
    # TAB 1: HFT EQUITIES SIMULATOR & AVELLANEDA-STOIKOV
    # =========================================================================
    def _build_sim_tab(self):
        layout = QHBoxLayout(self.tab_sim)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # --- Left Controls Column ---
        left_ctrl = QWidget()
        left_ctrl.setFixedWidth(345)
        l_layout = QVBoxLayout(left_ctrl)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(8)

        # 1. Simulation Loop Controls
        grp_sim_ctrl = QGroupBox("Simulation Controls")
        sc_layout = QVBoxLayout(grp_sim_ctrl)
        sc_layout.setSpacing(8)

        sc_layout.addWidget(QLabel("Order Flow Regime:"))
        self.cmb_regime = QComboBox()
        self.cmb_regime.addItem(FlowRegime.NOISE.value, FlowRegime.NOISE)
        self.cmb_regime.addItem(FlowRegime.MOMENTUM.value, FlowRegime.MOMENTUM)
        self.cmb_regime.addItem(FlowRegime.TOXIC.value, FlowRegime.TOXIC)
        self.cmb_regime.currentIndexChanged.connect(self.on_regime_changed)
        sc_layout.addWidget(self.cmb_regime)

        self.chk_ab_duel = QCheckBox("A/B Duel vs FixedSpread Baseline")
        self.chk_ab_duel.setChecked(True)
        self.chk_ab_duel.stateChanged.connect(self.update_sim_ui)
        sc_layout.addWidget(self.chk_ab_duel)

        self.chk_manual_mm = QCheckBox("Play as MM (W/S Skew, A/D Spread, Space Flat)")
        self.chk_manual_mm.setChecked(False)
        self.chk_manual_mm.stateChanged.connect(self.on_manual_mm_toggled)
        sc_layout.addWidget(self.chk_manual_mm)

        self.manual_skew_ticks = 0
        self.manual_hs_ticks = 2
        self.manual_ctrl_frame = QFrame()
        mc_lay = QHBoxLayout(self.manual_ctrl_frame)
        mc_lay.setContentsMargins(0, 0, 0, 0)
        mc_lay.setSpacing(4)
        for lbl, fn in [
            ("Skew- (S)", lambda: self._adjust_manual_quote(-1, 0)),
            ("Skew+ (W)", lambda: self._adjust_manual_quote(1, 0)),
            ("Tight (A)", lambda: self._adjust_manual_quote(0, -1)),
            ("Wide (D)", lambda: self._adjust_manual_quote(0, 1)),
            ("Flat", self.on_flatten_manual_inv),
        ]:
            b = QPushButton(lbl)
            b.setStyleSheet("padding: 4px 6px; font-size: 11px;")
            b.clicked.connect(fn)
            mc_lay.addWidget(b)
        self.manual_ctrl_frame.setVisible(False)
        sc_layout.addWidget(self.manual_ctrl_frame)

        self.btn_play = QPushButton("START AUTO-SIMULATION")
        self.btn_play.setObjectName("primaryBtn")
        self.btn_play.clicked.connect(self.toggle_simulation)
        sc_layout.addWidget(self.btn_play)

        h_step = QHBoxLayout()
        btn_step1 = QPushButton("Step +1")
        btn_step1.clicked.connect(lambda: self.step_sim_ticks(1))
        btn_step10 = QPushButton("Step +10")
        btn_step10.clicked.connect(lambda: self.step_sim_ticks(10))
        btn_reset_sim = QPushButton("Reset")
        btn_reset_sim.clicked.connect(self.reset_sim)
        h_step.addWidget(btn_step1)
        h_step.addWidget(btn_step10)
        h_step.addWidget(btn_reset_sim)
        sc_layout.addLayout(h_step)

        l_layout.addWidget(grp_sim_ctrl)

        # 2. Avellaneda-Stoikov & Latency Parameters
        grp_as = QGroupBox("Strategy & Network Latency")
        as_layout = QGridLayout(grp_as)
        as_layout.setVerticalSpacing(6)

        # Gamma (Risk Aversion)
        as_layout.addWidget(QLabel("Risk Aversion (γ):"), 0, 0)
        self.lbl_gamma_val = QLabel("0.10")
        self.lbl_gamma_val.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #d2a8ff;")
        as_layout.addWidget(self.lbl_gamma_val, 0, 1, Qt.AlignmentFlag.AlignRight)
        self.sld_gamma = QSlider(Qt.Orientation.Horizontal)
        self.sld_gamma.setRange(1, 100)  # 0.01 to 1.00
        self.sld_gamma.setValue(int(self.sim.mm.model.gamma * 100))
        self.sld_gamma.valueChanged.connect(self.on_as_params_changed)
        as_layout.addWidget(self.sld_gamma, 1, 0, 1, 2)

        # Sigma (Volatility)
        as_layout.addWidget(QLabel("Volatility (σ):"), 2, 0)
        self.lbl_sigma_val = QLabel("0.25")
        self.lbl_sigma_val.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e5ff;")
        as_layout.addWidget(self.lbl_sigma_val, 2, 1, Qt.AlignmentFlag.AlignRight)
        self.sld_sigma = QSlider(Qt.Orientation.Horizontal)
        self.sld_sigma.setRange(5, 80)  # 0.05 to 0.80
        self.sld_sigma.setValue(int(self.sim.mm.model.sigma * 100))
        self.sld_sigma.valueChanged.connect(self.on_as_params_changed)
        as_layout.addWidget(self.sld_sigma, 3, 0, 1, 2)

        # Kappa (Order Arrival Intensity)
        as_layout.addWidget(QLabel("Flow Intensity (κ):"), 4, 0)
        self.lbl_kappa_val = QLabel("1.50")
        self.lbl_kappa_val.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #ffd700;")
        as_layout.addWidget(self.lbl_kappa_val, 4, 1, Qt.AlignmentFlag.AlignRight)
        self.sld_kappa = QSlider(Qt.Orientation.Horizontal)
        self.sld_kappa.setRange(5, 50)  # 0.50 to 5.00
        self.sld_kappa.setValue(int(self.sim.mm.model.kappa * 10))
        self.sld_kappa.valueChanged.connect(self.on_as_params_changed)
        as_layout.addWidget(self.sld_kappa, 5, 0, 1, 2)

        # Network Latency (RTT ms)
        as_layout.addWidget(QLabel("Network Latency (RTT):"), 6, 0)
        self.lbl_latency_val = QLabel("2 ms")
        self.lbl_latency_val.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #ffab00;")
        as_layout.addWidget(self.lbl_latency_val, 6, 1, Qt.AlignmentFlag.AlignRight)
        self.sld_latency = QSlider(Qt.Orientation.Horizontal)
        self.sld_latency.setRange(0, 200)  # 0ms to 200ms RTT
        self.sld_latency.setValue(2)
        self.sld_latency.valueChanged.connect(self.on_as_params_changed)
        as_layout.addWidget(self.sld_latency, 7, 0, 1, 2)

        # Live Formula Readout
        self.lbl_as_math = QLabel("r = Mid - q·γ·σ²·τ")
        self.lbl_as_math.setWordWrap(True)
        self.lbl_as_math.setStyleSheet(
            "background-color: #0b0f14; border: 1px solid #262c36; border-radius: 6px; "
            "padding: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #c9d1d9;"
        )
        as_layout.addWidget(self.lbl_as_math, 8, 0, 1, 2)

        l_layout.addWidget(grp_as)

        # 3. Execution Tape
        grp_tape = QGroupBox("Live Execution Tape")
        tp_layout = QVBoxLayout(grp_tape)
        self.txt_tape = QTextEdit()
        self.txt_tape.setReadOnly(True)
        self.txt_tape.setStyleSheet(
            "background-color: #0b0f14; border: 1px solid #262c36; border-radius: 6px; "
            "color: #8b949e; font-family: 'JetBrains Mono', monospace; font-size: 11px;"
        )
        tp_layout.addWidget(self.txt_tape)
        l_layout.addWidget(grp_tape, stretch=1)

        layout.addWidget(left_ctrl)

        # --- Right Charts & KPI Strip ---
        right_panel = QWidget()
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(8)

        # KPI Cards Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        c_inv, self.lbl_t_inv, self.lbl_t_inv_sub = _make_kpi_card("Inventory (q)", "0 units", "#ffd700")
        c_spr, self.lbl_t_spr, self.lbl_t_spr_sub = _make_kpi_card("Spread Capture PnL", "$0.00", "#00e676")
        c_adv, self.lbl_t_adv, self.lbl_t_adv_sub = _make_kpi_card("Inventory / Adv. Sel.", "$0.00", "#ffa657")
        c_mtm, self.lbl_t_mtm, self.lbl_t_mtm_sub = _make_kpi_card("Total MTM PnL", "$0.00", "#58a6ff")
        kpi_row.addWidget(c_inv)
        kpi_row.addWidget(c_spr)
        kpi_row.addWidget(c_adv)
        kpi_row.addWidget(c_mtm)
        r_layout.addLayout(kpi_row)

        # Tick Inspector Bar (updates on chart hover)
        self.lbl_tick_inspector = QLabel("Hover over chart to inspect exact tick values (Mid, r, Bid/Ask, Inventory, PnL)")
        self.lbl_tick_inspector.setStyleSheet(
            "background-color: #0b0f14; border: 1px solid #262c36; border-radius: 5px; "
            "padding: 5px 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #8b949e;"
        )
        r_layout.addWidget(self.lbl_tick_inspector)

        # 3-Panel Synchronized Chart (almost full height & width)
        self.fig_sim = Figure(figsize=(12, 8.5), facecolor="#131820")
        self.canvas_sim = FigureCanvasQTAgg(self.fig_sim)
        self._crosshair_lines = []
        self._sim_axes = []
        self.canvas_sim.mpl_connect("motion_notify_event", self._on_sim_hover)
        r_layout.addWidget(self.canvas_sim, stretch=1)

        layout.addWidget(right_panel, stretch=1)

    def on_as_params_changed(self):
        gamma = self.sld_gamma.value() / 100.0
        sigma = self.sld_sigma.value() / 100.0
        kappa = self.sld_kappa.value() / 10.0
        rtt_ms = float(self.sld_latency.value())

        self.sim.mm.model.gamma = gamma
        self.sim.mm.model.sigma = sigma
        self.sim.mm.model.kappa = kappa
        self.sim.volatility = sigma
        self.sim.latency.feed_latency_ms = rtt_ms / 2.0
        self.sim.latency.order_latency_ms = rtt_ms / 2.0
        self.sim.latency.jitter_std_ms = max(0.1, rtt_ms * 0.05)

        self.lbl_gamma_val.setText(f"{gamma:.2f}")
        self.lbl_sigma_val.setText(f"{sigma:.2f}")
        self.lbl_kappa_val.setText(f"{kappa:.2f}")
        self.lbl_latency_val.setText(f"{int(rtt_ms)} ms")
        self._update_as_math_label()

    def _update_as_math_label(self):
        bid, ask, res_p = self.sim.mm.compute_quotes(self.sim.fair_price)
        skew = res_p - self.sim.fair_price
        hs = self.sim.mm.model.half_spread()
        self.lbl_as_math.setText(
            f"Mid: ${self.sim.fair_price:.2f}  |  Reservation r: ${res_p:.2f} (skew {skew:+.3f})\n"
            f"Half-Spread: ${hs:.3f}  |  Quotes: ${bid:.2f} / ${ask:.2f}"
        )

    def on_regime_changed(self):
        reg = self.cmb_regime.currentData()
        self.sim.flow_regime = reg
        self.set_narration(f"Order flow switched to {reg.value}.", "info")

    def toggle_simulation(self):
        if self.is_sim_running:
            self.sim_timer.stop()
            self.is_sim_running = False
            self.btn_play.setText("START AUTO-SIMULATION")
            self.btn_play.setStyleSheet("")
            self.set_narration("Simulation paused.", "info")
        else:
            self.sim_timer.start(300)
            self.is_sim_running = True
            self.btn_play.setText("PAUSE SIMULATION")
            self.btn_play.setStyleSheet("background-color: #d9534f; border-color: #ff5252; color: white; font-weight: 700;")
            self.set_narration("Live HFT simulation running (300ms/tick)...", "info")

    def on_manual_mm_toggled(self):
        active = self.chk_manual_mm.isChecked()
        self.manual_ctrl_frame.setVisible(active)
        if active:
            self.setFocus()
            self.set_narration(
                "Manual MM Mode ON: W/S = Skew quotes up/down, A/D = Tighten/Widen spread, Space = Flatten inventory.",
                "info",
            )
        else:
            self.set_narration("Switched back to Automated Avellaneda-Stoikov quoting.", "info")

    def _manual_bid_ask(self) -> tuple[float, float]:
        t = self.sim.tick_size
        center = self.sim.fair_price + (self.manual_skew_ticks * t)
        hs = max(1, self.manual_hs_ticks) * t
        return round(center - hs, 4), round(center + hs, 4)

    def _adjust_manual_quote(self, d_skew: int, d_hs: int):
        self.manual_skew_ticks = max(-10, min(10, self.manual_skew_ticks + d_skew))
        self.manual_hs_ticks = max(1, min(12, self.manual_hs_ticks + d_hs))
        b, a = self._manual_bid_ask()
        self.set_narration(
            f"Manual Quotes -> Skew: {self.manual_skew_ticks:+d} ticks | Half-Spread: {self.manual_hs_ticks} ticks (${b:.2f} / ${a:.2f})",
            "info",
        )

    def on_flatten_manual_inv(self):
        q = self.sim.flatten_mm_inventory()
        if abs(q) > 0:
            self.update_sim_ui()
            self.set_narration(f"Flattened {q:+.0f} units at market (1-tick crossing cost).", "success")

    def keyPressEvent(self, event):
        if self.chk_manual_mm.isChecked() and self.tabs.currentIndex() == 0:
            k = event.key()
            if k == Qt.Key.Key_W:
                self._adjust_manual_quote(1, 0)
                return
            elif k == Qt.Key.Key_S:
                self._adjust_manual_quote(-1, 0)
                return
            elif k == Qt.Key.Key_A:
                self._adjust_manual_quote(0, -1)
                return
            elif k == Qt.Key.Key_D:
                self._adjust_manual_quote(0, 1)
                return
            elif k == Qt.Key.Key_Space:
                self.on_flatten_manual_inv()
                return
        super().keyPressEvent(event)

    def on_sim_timer_tick(self):
        self.step_sim_ticks(1)

    def step_sim_ticks(self, count: int):
        for _ in range(count):
            cq = self._manual_bid_ask() if self.chk_manual_mm.isChecked() else None
            events = self.sim.step(auto_quote=(cq is None), custom_quotes=cq)
            step = self.sim.step_count
            if cq is not None:
                bid, ask = cq
                res_p = (bid + ask) / 2.0
            else:
                bid, ask, res_p = self.sim.mm.compute_quotes(self.sim.fair_price)
            micro = self.signal_engine.compute_micro_price(self.sim.book) or self.sim.fair_price
            bb = self.sim.book.best_bid() or bid
            ba = self.sim.book.best_ask() or ask

            self.history_steps.append(step)
            self.history_mids.append(self.sim.fair_price)
            self.history_res.append(res_p)
            self.history_micros.append(micro)
            self.history_bids.append(bb)
            self.history_asks.append(ba)
            self.history_inv.append(self.sim.mm.inventory)
            self.history_spr_pnl.append(self.sim.mm.spread_pnl)
            self.history_mtm_pnl.append(self.sim.mm.mark_to_market_pnl(self.sim.fair_price))
            self.history_bl_inv.append(self.sim.baseline_mm.inventory)
            self.history_bl_mtm_pnl.append(self.sim.baseline_mm.mark_to_market_pnl(self.sim.fair_price))

            for ev in events:
                if ev.event_type == "TRADE" and "trade" in ev.details:
                    tr = ev.details["trade"]
                    self.fill_records.append(FillRecord(step=step, side=tr.maker_side, price=tr.price, fair_at_fill=self.sim.fair_price))
                    is_stale = ev.details.get("stale_snipe", False)
                    if is_stale:
                        self.stale_fills.append((step, tr.price))
                        self.txt_tape.append(f"<span style='color:#ffab00; font-weight:bold;'>{ev.description}</span>")
                        self.set_narration(ev.description, "alert")
                    else:
                        if tr.maker_side == Side.BUY:
                            self.buy_fills.append((step, tr.price))
                        else:
                            self.sell_fills.append((step, tr.price))
                        self.txt_tape.append(f"<span style='color:#00e676;'>{ev.description}</span>")
                        self.set_narration(ev.description, "success")
                elif ev.event_type == "SHOCK":
                    self.txt_tape.append(f"<span style='color:#ff5252; font-weight:bold;'>{ev.description}</span>")
                    self.set_narration(ev.description, "alert")
                elif ev.event_type != "PRICE_MOVE":
                    self.txt_tape.append(f"• {ev.description}")

        self.update_sim_ui()
        self.update_dom_ui()
        self.update_analytics_ui()

    def update_sim_ui(self):
        inv = self.sim.mm.inventory
        spr = self.sim.mm.spread_pnl
        tot = self.sim.mm.mark_to_market_pnl(self.sim.fair_price)
        inv_pnl = tot - spr
        bl_tot = self.sim.baseline_mm.mark_to_market_pnl(self.sim.fair_price)
        show_ab = self.chk_ab_duel.isChecked()

        inv_color = "#ffd700" if abs(inv) < 10 else ("#00e676" if inv > 0 else "#ff5252")
        self.lbl_t_inv.setText(f"{inv:+.0f} units")
        self.lbl_t_inv.setStyleSheet(f"font-family: 'JetBrains Mono'; font-size: 17px; font-weight: 700; color: {inv_color};")
        self.lbl_t_inv_sub.setText(
            f"FixedSpread q: {self.sim.baseline_mm.inventory:+.0f}" if show_ab
            else f"Skew: {'DOWN (sell bias)' if inv > 0 else ('UP (buy bias)' if inv < 0 else 'Neutral')}"
        )

        self.lbl_t_spr.setText(f"${spr:,.2f}")
        self.lbl_t_spr_sub.setText(f"Fills: {self.sim.mm.trades_count} | Stale Snipes: {self.sim.stale_snipe_count}")

        adv_color = "#00e676" if inv_pnl >= 0 else "#ff5252"
        self.lbl_t_adv.setText(f"${inv_pnl:+,.2f}")
        self.lbl_t_adv.setStyleSheet(f"font-family: 'JetBrains Mono'; font-size: 17px; font-weight: 700; color: {adv_color};")
        self.lbl_t_adv_sub.setText("Total MTM - Spread")

        mtm_color = "#58a6ff" if tot >= 0 else "#ff5252"
        self.lbl_t_mtm.setText(f"${tot:,.2f}")
        self.lbl_t_mtm.setStyleSheet(f"font-family: 'JetBrains Mono'; font-size: 17px; font-weight: 700; color: {mtm_color};")
        self.lbl_t_mtm_sub.setText(
            f"FixedSpread MTM: ${bl_tot:,.2f}" if show_ab else f"Step #{self.sim.step_count}"
        )

        self._update_as_math_label()

        # --- 3-Panel Synchronized Plot ---
        self.fig_sim.clear()
        axes = self.fig_sim.subplots(
            3, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 0.9, 1.5], "hspace": 0.22}
        )
        ax1, ax2, ax3 = axes

        win = 80
        steps = self.history_steps[-win:]
        mids = self.history_mids[-win:]
        res = self.history_res[-win:]
        micros = self.history_micros[-win:]
        bids = self.history_bids[-win:]
        asks = self.history_asks[-win:]
        invs = self.history_inv[-win:]
        bl_invs = self.history_bl_inv[-win:]
        spr_pnls = self.history_spr_pnl[-win:]
        mtm_pnls = self.history_mtm_pnl[-win:]
        bl_mtm_pnls = self.history_bl_mtm_pnl[-win:]
        inv_pnls = [m - s for m, s in zip(mtm_pnls, spr_pnls)]

        min_step = steps[0] if steps else 0

        # Panel 1: Price, Reservation Price, Quotes & Fill Markers
        ax1.set_facecolor("#0b0f14")
        ax1.fill_between(steps, bids, asks, color="#58a6ff", alpha=0.06)
        ax1.plot(steps, mids, "-", color="#ffd700", label="Mid Price", linewidth=2.0)
        ax1.plot(steps, res, "-.", color="#d2a8ff", label="Reservation Price (r)", linewidth=1.6)
        ax1.plot(steps, micros, ":", color="#00e5ff", label="Micro-Price", linewidth=1.3, alpha=0.9)
        ax1.plot(steps, bids, "--", color="#00e676", label="MM Bid", linewidth=1.2, alpha=0.85)
        ax1.plot(steps, asks, "--", color="#ff5252", label="MM Ask", linewidth=1.2, alpha=0.85)

        bf_x = [s for s, _ in self.buy_fills if s >= min_step]
        bf_y = [p for s, p in self.buy_fills if s >= min_step]
        sf_x = [s for s, _ in self.sell_fills if s >= min_step]
        sf_y = [p for s, p in self.sell_fills if s >= min_step]
        st_x = [s for s, _ in self.stale_fills if s >= min_step]
        st_y = [p for s, p in self.stale_fills if s >= min_step]
        if bf_x:
            ax1.scatter(bf_x, bf_y, marker="^", color="#00e676", s=60, zorder=5, edgecolors="#0b0f14", label="Buy Fill")
        if sf_x:
            ax1.scatter(sf_x, sf_y, marker="v", color="#ff5252", s=60, zorder=5, edgecolors="#0b0f14", label="Sell Fill")
        if st_x:
            ax1.scatter(st_x, st_y, marker="X", color="#ffab00", s=85, zorder=6, edgecolors="#0b0f14", label="Stale Snipe")

        ax1.set_title("Mid Price, Reservation Price (r), Quotes & Fills", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax1.set_ylabel("Price ($)", color="#8b949e", fontsize=9)
        ax1.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left", ncol=4)

        # Panel 2: Inventory (q) + A/B FixedSpread Inventory
        ax2.set_facecolor("#0b0f14")
        bar_colors = ["#00e676" if q >= 0 else "#ff5252" for q in invs]
        ax2.bar(steps, invs, color=bar_colors, alpha=0.75, width=0.7, label="Avellaneda-Stoikov q")
        if show_ab:
            ax2.plot(steps, bl_invs, "--", color="#f778ba", linewidth=1.5, label="FixedSpread q")
            ax2.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left", ncol=2)
        ax2.axhline(0, color="#8b949e", linewidth=0.8, linestyle="--")
        ax2.set_title("Inventory (q) — Avellaneda-Stoikov vs FixedSpread", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax2.set_ylabel("Units", color="#8b949e", fontsize=9)

        # Panel 3: PnL Attribution + A/B FixedSpread MTM
        ax3.set_facecolor("#0b0f14")
        ax3.plot(steps, spr_pnls, "-", color="#00e676", label="A-S Spread Capture", linewidth=1.8)
        ax3.plot(steps, mtm_pnls, "-", color="#58a6ff", label="A-S Total MTM", linewidth=2.2)
        ax3.plot(steps, inv_pnls, "--", color="#ffa657", label="A-S Inventory Risk", linewidth=1.3)
        if show_ab:
            ax3.plot(steps, bl_mtm_pnls, "--", color="#f778ba", label="FixedSpread Total MTM", linewidth=1.8)
        ax3.fill_between(steps, spr_pnls, mtm_pnls, color="#ff5252", alpha=0.10)
        ax3.axhline(0, color="#8b949e", linewidth=0.8, linestyle="--")
        ax3.set_title("PnL Attribution & Strategy Duel (Avellaneda-Stoikov vs FixedSpread)", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax3.set_xlabel("Simulation Step", color="#8b949e", fontsize=9)
        ax3.set_ylabel("PnL ($)", color="#8b949e", fontsize=9)
        ax3.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left", ncol=4)

        self._sim_axes = list(axes)
        self._crosshair_lines = []
        for ax in axes:
            ax.tick_params(colors="#8b949e", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#262c36")
            ax.grid(True, color="#1c2128", linestyle="--", alpha=0.7)
            vl = ax.axvline(steps[-1] if steps else 0, color="#8b949e", linestyle=":", linewidth=1.0, alpha=0.0)
            self._crosshair_lines.append(vl)

        self.fig_sim.subplots_adjust(left=0.06, right=0.985, top=0.955, bottom=0.065)
        self.canvas_sim.draw()

    def _on_sim_hover(self, event):
        if event.inaxes not in self._sim_axes or event.xdata is None or not self.history_steps:
            return
        target_step = int(round(event.xdata))
        # Find nearest index in history_steps
        start = self.history_steps[0]
        idx = max(0, min(len(self.history_steps) - 1, target_step - start))
        st = self.history_steps[idx]
        mid = self.history_mids[idx]
        r_p = self.history_res[idx]
        b_p = self.history_bids[idx]
        a_p = self.history_asks[idx]
        q = self.history_inv[idx]
        spr = self.history_spr_pnl[idx]
        mtm = self.history_mtm_pnl[idx]

        for vl in self._crosshair_lines:
            vl.set_xdata([st, st])
            vl.set_alpha(0.65)
        self.canvas_sim.draw_idle()

        self.lbl_tick_inspector.setText(
            f"Step #{st}  |  Mid: ${mid:.2f}  |  r: ${r_p:.2f}  |  Quotes: ${b_p:.2f}/${a_p:.2f}  |  "
            f"Inv: {q:+.0f}  |  Spread: ${spr:,.2f}  |  MTM: ${mtm:,.2f}"
        )
        self.lbl_tick_inspector.setStyleSheet(
            "background-color: #0b0f14; border: 1px solid #30363d; border-radius: 5px; "
            "padding: 5px 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #e6edf3;"
        )

    def reset_sim(self):
        if self.is_sim_running:
            self.toggle_simulation()
        self.sim = MarketSimulator(
            initial_price=100.0,
            tick_size=0.05,
            volatility=self.sld_sigma.value() / 100.0,
            flow_regime=self.cmb_regime.currentData(),
        )
        self.on_as_params_changed()
        self.sim.step(auto_quote=True)
        self._init_sim_history()
        self.manual_dom_orders.clear()
        self.txt_tape.clear()
        self.update_sim_ui()
        self.update_dom_ui()
        self.set_narration("Simulator reset.", "info")

    # =========================================================================
    # TAB 2: DEPTH OF MARKET (DOM) & QUEUE PRIORITY
    # =========================================================================
    def _build_dom_tab(self):
        layout = QHBoxLayout(self.tab_dom)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Left: DOM Ladder Table
        dom_group = QGroupBox("Depth of Market (DOM) — Click Row to Place/Cancel Manual Order")
        dom_layout = QVBoxLayout(dom_group)

        dom_hint = QLabel("Click Bid column to post/cancel a 5-unit BUY limit; click Ask column for a 5-unit SELL limit.")
        dom_hint.setStyleSheet("color: #8b949e; font-size: 11px;")
        dom_layout.addWidget(dom_hint)

        self.table_dom = QTableWidget(0, 3)
        self.table_dom.setHorizontalHeaderLabels(["Bid Depth", "Price ($)", "Ask Depth"])
        self.table_dom.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_dom.verticalHeader().setVisible(False)
        self.table_dom.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_dom.cellClicked.connect(self.on_dom_cell_clicked)
        dom_layout.addWidget(self.table_dom)

        btn_resample = QPushButton("Reseed Order Book Depth")
        btn_resample.clicked.connect(self.on_reseed_book)
        dom_layout.addWidget(btn_resample)

        layout.addWidget(dom_group, stretch=1)

        # Right: Visual Queue & Market Sweeper
        queue_group = QGroupBox("FIFO Queue Priority (Best Bid & Best Ask)")
        q_layout = QVBoxLayout(queue_group)

        q_info = QLabel(
            "Exchange matching engines fill orders at the same price in strict FIFO order (top = head of line). "
            "Watch your queue position shrink as market orders sweep the top of the book."
        )
        q_info.setWordWrap(True)
        q_info.setStyleSheet("color: #8b949e; font-size: 11px;")
        q_layout.addWidget(q_info)

        self.fig_queue = Figure(figsize=(5.5, 5.2), facecolor="#131820")
        self.canvas_queue = FigureCanvasQTAgg(self.fig_queue)
        q_layout.addWidget(self.canvas_queue, stretch=1)

        # Market Sweeper Controls (Both Buy & Sell)
        sweep_box = QFrame()
        sweep_box.setStyleSheet("background-color: #0b0f14; border: 1px solid #262c36; border-radius: 6px; padding: 8px;")
        sw_layout = QHBoxLayout(sweep_box)

        sw_layout.addWidget(QLabel("Sweep Qty:"))
        self.spn_sweep_qty = QDoubleSpinBox()
        self.spn_sweep_qty.setRange(1.0, 50.0)
        self.spn_sweep_qty.setValue(12.0)
        sw_layout.addWidget(self.spn_sweep_qty)

        btn_sweep_buy = QPushButton("MARKET BUY")
        btn_sweep_buy.setObjectName("buyBtn")
        btn_sweep_buy.clicked.connect(lambda: self.on_sweep_market_order(Side.BUY))
        sw_layout.addWidget(btn_sweep_buy)

        btn_sweep_sell = QPushButton("MARKET SELL")
        btn_sweep_sell.setObjectName("sellBtn")
        btn_sweep_sell.clicked.connect(lambda: self.on_sweep_market_order(Side.SELL))
        sw_layout.addWidget(btn_sweep_sell)

        q_layout.addWidget(sweep_box)
        layout.addWidget(queue_group, stretch=1)

    def _draw_queue_subplot(self, ax, orders: list[Order], title: str):
        ax.set_facecolor("#0b0f14")
        if not orders:
            ax.text(0.5, 0.5, "No resting orders at this level", ha="center", va="center", color="#8b949e", transform=ax.transAxes)
            ax.set_title(title, color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
            return

        names = []
        colors = []
        ahead_mm = 0.0
        seen_mm = False
        for o in orders:
            if o.is_mm:
                names.append("★ MM_BOT")
                colors.append("#1f6feb")
                seen_mm = True
            elif o.trader_id == "YOU_MANUAL":
                names.append("● YOU (Manual)")
                colors.append("#00e5ff")
            else:
                names.append(o.trader_id)
                colors.append("#2b323d")
                if not seen_mm:
                    ahead_mm += o.quantity

        vols = [o.quantity for o in orders]
        y_pos = np.arange(len(names))
        ax.barh(y_pos, vols, color=colors, edgecolor="#30363d", height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"#{i+1} {n}" for i, n in enumerate(names)], color="#c9d1d9", fontsize=9)
        ax.invert_yaxis()

        max_v = max(vols) if vols else 1.0
        ax.set_xlim(0, max_v * 1.25)
        for i, v in enumerate(vols):
            ax.text(v + max_v * 0.02, i, f"{v:.0f}", va="center", color="#f0f6fc", fontsize=8, fontweight="bold")

        suffix = f"  |  Ahead of MM: {ahead_mm:.0f}" if seen_mm else ""
        ax.set_title(f"{title}{suffix}", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax.tick_params(colors="#8b949e", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#262c36")
        ax.grid(True, color="#1c2128", linestyle="--", alpha=0.6, axis="x")

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

            b_orders = book.get_level_orders(Side.BUY, p) if b_vol > 0 else []
            a_orders = book.get_level_orders(Side.SELL, p) if a_vol > 0 else []

            b_tag = (" ★" if any(o.is_mm for o in b_orders) else "") + (" ●" if any(o.trader_id == "YOU_MANUAL" for o in b_orders) else "")
            a_tag = (" ★" if any(o.is_mm for o in a_orders) else "") + (" ●" if any(o.trader_id == "YOU_MANUAL" for o in a_orders) else "")

            b_item = QTableWidgetItem(f"{b_vol:.0f}{b_tag}" if b_vol > 0 else "")
            b_item.setData(Qt.ItemDataRole.UserRole, p)
            if b_vol > 0:
                b_item.setForeground(QColor("#00e676"))
                b_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            p_item = QTableWidgetItem(f"${p:.2f}")
            p_item.setData(Qt.ItemDataRole.UserRole, p)
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            p_item.setFont(QFont("JetBrains Mono", 11, QFont.Weight.Bold))

            a_item = QTableWidgetItem(f"{a_vol:.0f}{a_tag}" if a_vol > 0 else "")
            a_item.setData(Qt.ItemDataRole.UserRole, p)
            if a_vol > 0:
                a_item.setForeground(QColor("#ff5252"))
                a_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.table_dom.setItem(r, 0, b_item)
            self.table_dom.setItem(r, 1, p_item)
            self.table_dom.setItem(r, 2, a_item)

        # Dual FIFO Queue Canvas (Best Bid & Best Ask)
        self.fig_queue.clear()
        ax_bid = self.fig_queue.add_subplot(211)
        ax_ask = self.fig_queue.add_subplot(212)

        bb = book.best_bid()
        ba = book.best_ask()
        bid_orders = book.get_level_orders(Side.BUY, bb) if bb is not None else []
        ask_orders = book.get_level_orders(Side.SELL, ba) if ba is not None else []

        self._draw_queue_subplot(ax_bid, bid_orders, f"Best Bid Queue (${bb:.2f})" if bb is not None else "Best Bid Queue (Empty)")
        self._draw_queue_subplot(ax_ask, ask_orders, f"Best Ask Queue (${ba:.2f})" if ba is not None else "Best Ask Queue (Empty)")

        self.fig_queue.tight_layout()
        self.canvas_queue.draw()

        # Header Consensus Barometer
        cs = self.signal_engine.evaluate_consensus(book)
        if cs:
            self.micro_price_lbl.setText(
                f"Micro: ${cs.micro_price:.4f} | Mid: ${cs.mid_price:.2f} | OBI: {cs.order_book_imbalance:+.2f}"
            )
            c_text = f"CONSENSUS: {cs.regime.value} ({cs.confidence_pct:.0f}%)"
            self.consensus_pill.setText(c_text)
            c_color = "#00e676" if "BUY" in cs.regime.value else ("#ff5252" if "SELL" in cs.regime.value else "#00e5ff")
            self.consensus_pill.setStyleSheet(
                f"background-color: rgba(255,255,255,0.04); border: 1px solid {c_color}; "
                f"color: {c_color}; font-weight: 700; font-size: 11px; padding: 5px 12px; border-radius: 6px;"
            )

    def on_dom_cell_clicked(self, row: int, col: int):
        item = self.table_dom.item(row, 1)
        if item is None:
            return
        price = item.data(Qt.ItemDataRole.UserRole)
        if price is None:
            return

        if col == 0:
            side = Side.BUY
        elif col == 2:
            side = Side.SELL
        else:
            mid = self.sim.book.mid_price() or self.sim.fair_price
            side = Side.BUY if price <= mid else Side.SELL

        key = (side, price)
        if key in self.manual_dom_orders:
            oid = self.manual_dom_orders.pop(key)
            self.sim.book.cancel_order(oid)
            self.set_narration(f"Cancelled manual {side.value} order at ${price:.2f}.", "info")
        else:
            oid = f"YOU_{uuid.uuid4().hex[:6]}"
            order = Order(oid, "YOU_MANUAL", side, price, 5.0, self.sim.current_time, is_mm=False)
            trades = self.sim.book.add_limit_order(order)
            if not trades:
                self.manual_dom_orders[key] = oid
                self.set_narration(f"Posted manual {side.value} limit (5 units @ ${price:.2f}) at back of FIFO queue.", "info")
            else:
                self.set_narration(f"Manual {side.value} order @ ${price:.2f} crossed the spread and filled immediately!", "success")

        self.update_dom_ui()

    def on_sweep_market_order(self, side: Side):
        qty = self.spn_sweep_qty.value()
        trades, _ = self.sim.book.execute_market_order("AggressiveTaker", side, qty, self.sim.current_time)
        self.update_dom_ui()

        if trades:
            filled_qty = sum(t.quantity for t in trades)
            avg_px = sum(t.price * t.quantity for t in trades) / filled_qty
            mm_fills = sum(t.quantity for t in trades if t.maker_trader_id == self.sim.mm.trader_id)
            msg = f"Market {side.value} swept {filled_qty:.0f} units @ avg ${avg_px:.2f}."
            if mm_fills > 0:
                msg += f" MM filled for {mm_fills:.0f} units!"
            self.set_narration(msg, "success" if mm_fills > 0 else "info")
        else:
            self.set_narration(f"Book empty on {'Ask' if side == Side.BUY else 'Bid'} side.", "alert")

    def on_reseed_book(self):
        self.sim._seed_background_liquidity()
        self.update_dom_ui()
        self.set_narration("Order book depth replenished with background liquidity.", "info")

    # =========================================================================
    # TAB 3: OPTIONS MARKET MAKING & DELTA HEDGING
    # =========================================================================
    def _build_options_tab(self):
        layout = QHBoxLayout(self.tab_options)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # --- Left Column: Controls ---
        left_panel = QWidget()
        left_panel.setFixedWidth(345)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        grp_contract = QGroupBox("Option Contract & Pricing")
        c_layout = QGridLayout(grp_contract)

        self.rad_call = QRadioButton("CALL")
        self.rad_call.setChecked(True)
        self.rad_put = QRadioButton("PUT")
        self.rad_call.toggled.connect(self.update_options_ui)
        h_type = QHBoxLayout()
        h_type.addWidget(self.rad_call)
        h_type.addWidget(self.rad_put)
        c_layout.addWidget(QLabel("Type:"), 0, 0)
        c_layout.addLayout(h_type, 0, 1)

        c_layout.addWidget(QLabel("Strike ($):"), 1, 0)
        self.spn_strike = QDoubleSpinBox()
        self.spn_strike.setRange(50.0, 150.0)
        self.spn_strike.setValue(105.0)
        self.spn_strike.setSingleStep(2.5)
        self.spn_strike.valueChanged.connect(self.update_options_ui)
        c_layout.addWidget(self.spn_strike, 1, 1)

        c_layout.addWidget(QLabel("Expiry (Days):"), 2, 0)
        self.spn_expiry = QSpinBox()
        self.spn_expiry.setRange(1, 365)
        self.spn_expiry.setValue(30)
        self.spn_expiry.valueChanged.connect(self.update_options_ui)
        c_layout.addWidget(self.spn_expiry, 2, 1)

        c_layout.addWidget(QLabel("Implied Vol (%):"), 3, 0)
        self.spn_vol = QDoubleSpinBox()
        self.spn_vol.setRange(0.05, 1.50)
        self.spn_vol.setValue(0.25)
        self.spn_vol.setSingleStep(0.05)
        self.spn_vol.valueChanged.connect(self.update_options_ui)
        c_layout.addWidget(self.spn_vol, 3, 1)

        self.opt_theo_lbl = QLabel("Theo: $2.54 | Δ: +0.38")
        self.opt_theo_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e5ff; padding: 4px 0;")
        c_layout.addWidget(self.opt_theo_lbl, 4, 0, 1, 2)

        btn_buy_opt = QPushButton("BUY 10 CONTRACTS")
        btn_buy_opt.setObjectName("buyBtn")
        btn_buy_opt.clicked.connect(self.on_buy_options)
        btn_sell_opt = QPushButton("SELL 10 CONTRACTS")
        btn_sell_opt.setObjectName("sellBtn")
        btn_sell_opt.clicked.connect(self.on_sell_options)

        h_trade = QHBoxLayout()
        h_trade.addWidget(btn_buy_opt)
        h_trade.addWidget(btn_sell_opt)
        c_layout.addLayout(h_trade, 5, 0, 1, 2)

        left_layout.addWidget(grp_contract)

        grp_market = QGroupBox("Simulate Underlying & Time")
        m_layout = QVBoxLayout(grp_market)

        self.lbl_spot_s = QLabel(f"Underlying Spot (S): ${self.underlying_s:.2f}")
        self.lbl_spot_s.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 13px; font-weight: 700; color: #ffd700;")
        m_layout.addWidget(self.lbl_spot_s)

        h_spot_btns = QHBoxLayout()
        for delta_s, text in [(-5.0, "-$5"), (-1.0, "-$1"), (1.0, "+$1"), (5.0, "+$5")]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, ds=delta_s: self.move_underlying(ds))
            h_spot_btns.addWidget(b)
        m_layout.addLayout(h_spot_btns)

        btn_theta_day = QPushButton("Advance +1 Day (Theta Decay)")
        btn_theta_day.clicked.connect(self.pass_one_day)
        m_layout.addWidget(btn_theta_day)

        left_layout.addWidget(grp_market)

        grp_hedge = QGroupBox("Delta-Neutral Hedging")
        h_layout = QVBoxLayout(grp_hedge)

        self.hedge_status_lbl = QLabel("Portfolio is Delta-Neutral")
        self.hedge_status_lbl.setWordWrap(True)
        h_layout.addWidget(self.hedge_status_lbl)

        self.btn_hedge = QPushButton("EXECUTE DELTA HEDGE")
        self.btn_hedge.setObjectName("primaryBtn")
        self.btn_hedge.clicked.connect(self.on_execute_delta_hedge)
        h_layout.addWidget(self.btn_hedge)

        btn_reset_port = QPushButton("Reset Portfolio")
        btn_reset_port.clicked.connect(self.reset_options_port)
        h_layout.addWidget(btn_reset_port)

        left_layout.addWidget(grp_hedge)
        left_layout.addStretch()

        layout.addWidget(left_panel)

        # --- Right Column: Greeks, Payoff + Portfolio PnL, Positions ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        g_row = QHBoxLayout()
        g_row.setSpacing(8)
        c_d, self.lbl_g_delta, _ = _make_kpi_card("Net Delta", "+0.0 shs", "#00e5ff")
        c_g, self.lbl_g_gamma, _ = _make_kpi_card("Net Gamma", "+0.0000", "#ffd700")
        c_v, self.lbl_g_vega, _ = _make_kpi_card("Net Vega", "$+0.0", "#d2a8ff")
        c_t, self.lbl_g_theta, _ = _make_kpi_card("Net Theta", "$+0.0/d", "#00e676")
        g_row.addWidget(c_d)
        g_row.addWidget(c_g)
        g_row.addWidget(c_v)
        g_row.addWidget(c_t)
        right_layout.addLayout(g_row)

        self.fig_options = Figure(figsize=(7, 5.0), facecolor="#131820")
        self.canvas_options = FigureCanvasQTAgg(self.fig_options)
        right_layout.addWidget(self.canvas_options, stretch=2)

        self.table_positions = QTableWidget(0, 5)
        self.table_positions.setHorizontalHeaderLabels(["Instrument", "Qty", "Current Price", "Market Value", "Net Delta"])
        self.table_positions.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_positions.verticalHeader().setVisible(False)
        self.table_positions.setMaximumHeight(160)
        right_layout.addWidget(self.table_positions)

        layout.addWidget(right_panel, stretch=1)

    def update_options_ui(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        is_call = self.rad_call.isChecked()
        otype = OptionType.CALL if is_call else OptionType.PUT

        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        g = BlackScholesEngine.greeks(self.underlying_s, k, 0.04, vol, tau, otype)
        self.opt_theo_lbl.setText(f"Theo: ${theo:.2f} | Δ: {g.delta:+.3f} | Γ: {g.gamma:.4f}")

        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, vol)
        nd = net_g["net_delta"]
        needed = net_g["hedge_shares_needed"]

        self.lbl_g_delta.setText(f"{nd:+.1f} shs")
        self.lbl_g_gamma.setText(f"{net_g['net_gamma']:+.4f}")
        self.lbl_g_vega.setText(f"${net_g['net_vega']:+.1f}")
        self.lbl_g_theta.setText(f"${net_g['net_theta']:+.1f}/d")

        if abs(needed) > 0.0:
            self.hedge_status_lbl.setText(f"Net Delta: {nd:+.1f} | Action: {'BUY' if needed>0 else 'SELL'} {abs(needed):.0f} shares")
            self.hedge_status_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #ff7b72;")
        else:
            self.hedge_status_lbl.setText("Portfolio is Delta-Neutral (Δ ≈ 0)")
            self.hedge_status_lbl.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e676;")

        # 2-Panel Plot: Option Curve + Portfolio PnL Curve
        self.fig_options.clear()
        ax1, ax2 = self.fig_options.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.28})

        s_range = np.linspace(max(10.0, k - 30.0), k + 30.0, 80)
        now_prices = [BlackScholesEngine.price(s_i, k, 0.04, vol, tau, otype) for s_i in s_range]
        exp_prices = [BlackScholesEngine.price(s_i, k, 0.04, vol, 0.0, otype) for s_i in s_range]
        port_pnls = [self.options_port.mark_to_market(s_i, 0.04, vol) - self.initial_options_cash for s_i in s_range]
        cur_port_pnl = self.options_port.mark_to_market(self.underlying_s, 0.04, vol) - self.initial_options_cash

        ax1.set_facecolor("#0b0f14")
        ax1.plot(s_range, exp_prices, "--", color="#6e7681", label="Expiry Payoff", linewidth=1.4)
        ax1.plot(s_range, now_prices, "-", color="#00e5ff", label=f"Today ({self.spn_expiry.value()}d)", linewidth=2.2)
        ax1.plot([self.underlying_s], [theo], "o", color="#ffd700", markersize=8, label=f"Spot ${self.underlying_s:.2f}")
        ax1.axvline(self.underlying_s, color="#ffd700", linestyle=":", alpha=0.4)
        ax1.axvline(k, color="#8b949e", linestyle="--", alpha=0.3)
        ax1.set_title(f"{'CALL' if is_call else 'PUT'} Value Profile (Strike ${k:.2f}, IV {vol*100:.0f}%)", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax1.set_ylabel("Option ($)", color="#8b949e", fontsize=9)
        ax1.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left")

        ax2.set_facecolor("#0b0f14")
        ax2.plot(s_range, port_pnls, "-", color="#58a6ff", label="Portfolio MTM PnL", linewidth=2.2)
        ax2.plot([self.underlying_s], [cur_port_pnl], "o", color="#ffd700", markersize=8)
        ax2.axhline(0, color="#8b949e", linestyle="--", alpha=0.5)
        ax2.axvline(self.underlying_s, color="#ffd700", linestyle=":", alpha=0.4)
        ax2.set_title("Portfolio PnL vs Underlying Price (Shows Delta Slope & Gamma Curvature)", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax2.set_xlabel("Underlying Stock Price ($)", color="#8b949e", fontsize=9)
        ax2.set_ylabel("Port PnL ($)", color="#8b949e", fontsize=9)
        ax2.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left")

        for ax in (ax1, ax2):
            ax.tick_params(colors="#8b949e", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#262c36")
            ax.grid(True, color="#1c2128", linestyle="--", alpha=0.7)

        self.fig_options.subplots_adjust(left=0.10, right=0.98, top=0.93, bottom=0.10)
        self.canvas_options.draw()

        # Positions Table
        self.table_positions.setRowCount(0)
        r_idx = self.table_positions.rowCount()
        self.table_positions.insertRow(r_idx)
        self.table_positions.setItem(r_idx, 0, QTableWidgetItem(f"Underlying ({self.options_port.underlying_symbol})"))
        self.table_positions.setItem(r_idx, 1, QTableWidgetItem(f"{self.options_port.underlying_shares:+.0f} shs"))
        self.table_positions.setItem(r_idx, 2, QTableWidgetItem(f"${self.underlying_s:.2f}"))
        self.table_positions.setItem(r_idx, 3, QTableWidgetItem(f"${self.options_port.underlying_shares * self.underlying_s:,.2f}"))
        self.table_positions.setItem(r_idx, 4, QTableWidgetItem(f"{self.options_port.underlying_shares:+.1f}"))

        for pos in self.options_port.positions:
            c = pos.contract
            cur_p = BlackScholesEngine.price(self.underlying_s, c.strike, 0.04, vol, c.expiry_years, c.option_type)
            cg = BlackScholesEngine.greeks(self.underlying_s, c.strike, 0.04, vol, c.expiry_years, c.option_type)
            r_idx = self.table_positions.rowCount()
            self.table_positions.insertRow(r_idx)
            self.table_positions.setItem(r_idx, 0, QTableWidgetItem(f"{c.option_type.value} ${c.strike:.1f} ({int(c.expiry_years*365)}d)"))
            self.table_positions.setItem(r_idx, 1, QTableWidgetItem(f"{pos.contracts_count:+} cts"))
            self.table_positions.setItem(r_idx, 2, QTableWidgetItem(f"${cur_p:.2f}"))
            self.table_positions.setItem(r_idx, 3, QTableWidgetItem(f"${pos.contracts_count * cur_p * c.contract_size:,.2f}"))
            self.table_positions.setItem(r_idx, 4, QTableWidgetItem(f"{cg.delta * pos.contracts_count * c.contract_size:+.1f}"))

    def on_sell_options(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        otype = OptionType.CALL if self.rad_call.isChecked() else OptionType.PUT
        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        c = OptionContract(otype, k, tau)
        self.options_port.add_trade(c, -10, theo)
        self.update_options_ui()
        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, vol)
        self.set_narration(
            f"Sold 10 {otype.value} contracts @ ${theo:.2f}. Net Delta is {net_g['net_delta']:+.1f} shs — click EXECUTE DELTA HEDGE to flatten slope.",
            "alert",
        )

    def on_buy_options(self):
        k = self.spn_strike.value()
        tau = self.spn_expiry.value() / 365.0
        vol = self.spn_vol.value()
        otype = OptionType.CALL if self.rad_call.isChecked() else OptionType.PUT
        theo = BlackScholesEngine.price(self.underlying_s, k, 0.04, vol, tau, otype)
        c = OptionContract(otype, k, tau)
        self.options_port.add_trade(c, 10, theo)
        self.update_options_ui()
        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, vol)
        self.set_narration(
            f"Bought 10 {otype.value} contracts @ ${theo:.2f}. Net Delta is {net_g['net_delta']:+.1f} shs.",
            "info",
        )

    def move_underlying(self, delta_s: float):
        self.underlying_s = max(10.0, self.underlying_s + delta_s)
        self.lbl_spot_s.setText(f"Underlying Spot (S): ${self.underlying_s:.2f}")
        self.update_options_ui()
        net_g = self.options_port.net_greeks(self.underlying_s, 0.04, self.spn_vol.value())
        self.set_narration(
            f"Spot moved to ${self.underlying_s:.2f}. Gamma shifted Net Delta to {net_g['net_delta']:+.1f} shs — re-hedge to stay neutral.",
            "info",
        )

    def pass_one_day(self):
        for pos in self.options_port.positions:
            pos.contract.expiry_years = max(0.0, pos.contract.expiry_years - (1.0 / 365.0))
        cur_d = self.spn_expiry.value()
        if cur_d > 1:
            self.spn_expiry.setValue(cur_d - 1)
        self.update_options_ui()
        self.set_narration("1 calendar day elapsed (Theta decay applied).", "info")

    def on_execute_delta_hedge(self):
        vol = self.spn_vol.value()
        needed = self.options_port.execute_delta_hedge(self.underlying_s, 0.04, vol)
        self.update_options_ui()
        if abs(needed) > 0:
            action = "BOUGHT" if needed > 0 else "SOLD"
            self.set_narration(
                f"Hedge executed: {action} {abs(needed):.0f} shares @ ${self.underlying_s:.2f}. Portfolio PnL curve is now flat at spot.",
                "success",
            )
        else:
            self.set_narration("Portfolio is already delta-neutral.", "info")

    def reset_options_port(self):
        self.options_port = OptionsPortfolio(initial_cash=self.initial_options_cash)
        self.underlying_s = 100.0
        self.lbl_spot_s.setText(f"Underlying Spot (S): ${self.underlying_s:.2f}")
        self.update_options_ui()
        self.set_narration("Options portfolio reset to $100,000 cash.", "info")

    # =========================================================================
    # TAB 4: ANALYTICS — POST-FILL MARKOUT & MONTE CARLO DUEL
    # =========================================================================
    def _build_analytics_tab(self):
        layout = QHBoxLayout(self.tab_analytics)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Left Controls
        left = QWidget()
        left.setFixedWidth(340)
        l_lay = QVBoxLayout(left)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(8)

        grp_mk = QGroupBox("Post-Fill Markout Diagnostic")
        mk_lay = QVBoxLayout(grp_mk)
        mk_info = QLabel(
            "Measures average signed price move (0 to 10 ticks) AFTER your fills.\n\n"
            "• Flat / positive curve = healthy spread capture.\n"
            "• Dropping below $0 = adverse selection (toxic flow or stale quotes)."
        )
        mk_info.setWordWrap(True)
        mk_info.setStyleSheet("color: #8b949e; font-size: 11px;")
        mk_lay.addWidget(mk_info)
        self.lbl_markout_fills = QLabel("Recorded Fills: 0")
        self.lbl_markout_fills.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: 700; color: #00e5ff;")
        mk_lay.addWidget(self.lbl_markout_fills)
        l_lay.addWidget(grp_mk)

        grp_mc = QGroupBox("Batch Monte Carlo Duel (Uses Current Tab 1 Params)")
        mc_lay = QGridLayout(grp_mc)

        mc_lay.addWidget(QLabel("Paths:"), 0, 0)
        self.spn_mc_paths = QSpinBox()
        self.spn_mc_paths.setRange(5, 100)
        self.spn_mc_paths.setValue(25)
        mc_lay.addWidget(self.spn_mc_paths, 0, 1)

        mc_lay.addWidget(QLabel("Ticks / Path:"), 1, 0)
        self.spn_mc_steps = QSpinBox()
        self.spn_mc_steps.setRange(50, 1000)
        self.spn_mc_steps.setSingleStep(50)
        self.spn_mc_steps.setValue(200)
        mc_lay.addWidget(self.spn_mc_steps, 1, 1)

        btn_run_mc = QPushButton("RUN MONTE CARLO DUEL")
        btn_run_mc.setObjectName("primaryBtn")
        btn_run_mc.clicked.connect(self.on_run_monte_carlo)
        mc_lay.addWidget(btn_run_mc, 2, 0, 1, 2)

        l_lay.addWidget(grp_mc)
        l_lay.addStretch()
        layout.addWidget(left)

        # Right Charts & Summary KPIs
        right = QWidget()
        r_lay = QVBoxLayout(right)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(8)

        mc_kpis = QHBoxLayout()
        mc_kpis.setSpacing(8)
        c1, self.lbl_mc_as_mean, self.lbl_mc_as_sub = _make_kpi_card("A-S Mean PnL", "—", "#58a6ff")
        c2, self.lbl_mc_fx_mean, self.lbl_mc_fx_sub = _make_kpi_card("FixedSpread Mean PnL", "—", "#f778ba")
        c3, self.lbl_mc_as_dd, self.lbl_mc_as_dd_sub = _make_kpi_card("A-S Avg Max DD", "—", "#00e676")
        c4, self.lbl_mc_fx_dd, self.lbl_mc_fx_dd_sub = _make_kpi_card("Fixed Avg Max DD", "—", "#ff5252")
        mc_kpis.addWidget(c1)
        mc_kpis.addWidget(c2)
        mc_kpis.addWidget(c3)
        mc_kpis.addWidget(c4)
        r_lay.addLayout(mc_kpis)

        self.fig_analytics = Figure(figsize=(10, 7.5), facecolor="#131820")
        self.canvas_analytics = FigureCanvasQTAgg(self.fig_analytics)
        r_lay.addWidget(self.canvas_analytics, stretch=1)

        layout.addWidget(right, stretch=1)

    def on_run_monte_carlo(self):
        n_paths = self.spn_mc_paths.value()
        n_steps = self.spn_mc_steps.value()
        self.last_mc_result = run_monte_carlo_duel(
            n_paths=n_paths,
            n_steps=n_steps,
            flow_regime=self.cmb_regime.currentData(),
            gamma=self.sld_gamma.value() / 100.0,
            sigma=self.sld_sigma.value() / 100.0,
            kappa=self.sld_kappa.value() / 10.0,
            rtt_ms=float(self.sld_latency.value()),
        )
        s = self.last_mc_result.summary()
        self.lbl_mc_as_mean.setText(f"${s['as']['mean_pnl']:,.2f}")
        self.lbl_mc_as_sub.setText(f"Sharpe: {s['as']['sharpe']:.2f} | Max|q|: {s['as']['avg_max_inv']:.1f}")
        self.lbl_mc_fx_mean.setText(f"${s['fixed']['mean_pnl']:,.2f}")
        self.lbl_mc_fx_sub.setText(f"Sharpe: {s['fixed']['sharpe']:.2f} | Max|q|: {s['fixed']['avg_max_inv']:.1f}")
        self.lbl_mc_as_dd.setText(f"${s['as']['avg_max_dd']:,.2f}")
        self.lbl_mc_fx_dd.setText(f"${s['fixed']['avg_max_dd']:,.2f}")

        self.update_analytics_ui()
        self.set_narration(
            f"Monte Carlo complete ({n_paths}×{n_steps} ticks): A-S Mean ${s['as']['mean_pnl']:,.2f} vs FixedSpread ${s['fixed']['mean_pnl']:,.2f}.",
            "success" if s["as"]["mean_pnl"] >= s["fixed"]["mean_pnl"] else "info",
        )

    def update_analytics_ui(self):
        self.lbl_markout_fills.setText(f"Recorded Fills: {len(self.fill_records)}")
        self.fig_analytics.clear()
        ax1, ax2 = self.fig_analytics.subplots(2, 1, gridspec_kw={"hspace": 0.32})

        # Top: Live Markout Curve
        ax1.set_facecolor("#0b0f14")
        horizons = (0, 1, 3, 5, 10)
        start_step = self.history_steps[0] if self.history_steps else 0
        curve = compute_markout_curve(self.fill_records, self.history_mids, start_step=start_step, horizons=horizons)
        xs = list(horizons)
        ys = [curve[h] for h in xs]
        ax1.plot(xs, ys, "-o", color="#00e5ff", linewidth=2.2, markersize=7, label="Avg Signed Markout ($)")
        ax1.fill_between(xs, 0, ys, where=[y >= 0 for y in ys], color="#00e676", alpha=0.15, interpolate=True)
        ax1.fill_between(xs, 0, ys, where=[y < 0 for y in ys], color="#ff5252", alpha=0.15, interpolate=True)
        ax1.axhline(0, color="#8b949e", linestyle="--", linewidth=1.0)
        ax1.set_title("Live Post-Fill Markout Curve (Adverse Selection Diagnostic)", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax1.set_xlabel("Ticks After Fill", color="#8b949e", fontsize=9)
        ax1.set_ylabel("Avg Edge ($)", color="#8b949e", fontsize=9)
        ax1.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper right")

        # Bottom: Monte Carlo PnL Distribution
        ax2.set_facecolor("#0b0f14")
        if self.last_mc_result is not None:
            ax2.hist(self.last_mc_result.as_mtms, bins=12, alpha=0.65, color="#58a6ff", label="Avellaneda-Stoikov MTM")
            ax2.hist(self.last_mc_result.fixed_mtms, bins=12, alpha=0.55, color="#f778ba", label="FixedSpread MTM")
            ax2.axvline(0, color="#8b949e", linestyle="--", linewidth=1.0)
            ax2.legend(facecolor="#131820", edgecolor="#262c36", labelcolor="#c9d1d9", fontsize=8, loc="upper left")
        else:
            ax2.text(0.5, 0.5, "Click 'RUN MONTE CARLO DUEL' to compare PnL distributions", ha="center", va="center", color="#8b949e", transform=ax2.transAxes)
        ax2.set_title("Monte Carlo Final MTM PnL Distribution (A-S vs FixedSpread)", color="#f0f6fc", fontsize=10, fontweight="bold", loc="left")
        ax2.set_xlabel("Final MTM PnL ($)", color="#8b949e", fontsize=9)
        ax2.set_ylabel("Paths", color="#8b949e", fontsize=9)

        for ax in (ax1, ax2):
            ax.tick_params(colors="#8b949e", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#262c36")
            ax.grid(True, color="#1c2128", linestyle="--", alpha=0.7)

        self.fig_analytics.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.08)
        self.canvas_analytics.draw()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
