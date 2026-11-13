"""Dark Institutional Styling & QSS Themes for MMSim Desktop GUI."""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #0b0f14;
    color: #e6edf3;
}

QWidget {
    font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
    color: #c9d1d9;
}

/* Top Header & KPI Cards */
QFrame#headerFrame {
    background-color: #131820;
    border: 1px solid #262c36;
    border-radius: 8px;
}

QFrame#kpiCard {
    background-color: #131820;
    border: 1px solid #262c36;
    border-radius: 8px;
    padding: 8px 12px;
}

QLabel#kpiTitle {
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

QLabel#kpiValue {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #f0f6fc;
}

QLabel#kpiSub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #8b949e;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #262c36;
    background: #131820;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #0b0f14;
    border: 1px solid #262c36;
    border-bottom: none;
    padding: 9px 20px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 12px;
    color: #8b949e;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #131820;
    color: #58a6ff;
    border-color: #262c36;
    border-top: 2px solid #58a6ff;
}

QTabBar::tab:hover {
    color: #f0f6fc;
}

/* Group Boxes / Cards */
QGroupBox {
    background-color: #131820;
    border: 1px solid #262c36;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 700;
    font-size: 12px;
    color: #79c0ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 2px 8px;
    background-color: #131820;
    border: 1px solid #262c36;
    border-radius: 4px;
}

/* Push Buttons */
QPushButton {
    background-color: #1f252e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 12px;
    color: #c9d1d9;
}

QPushButton:hover {
    background-color: #2b323d;
    color: #f0f6fc;
    border-color: #58a6ff;
}

QPushButton:pressed {
    background-color: #131820;
}

/* Primary Action Button */
QPushButton#primaryBtn {
    background-color: #1f6feb;
    border: 1px solid #388bfd;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#primaryBtn:hover {
    background-color: #388bfd;
}

/* Success Button */
QPushButton#buyBtn {
    background-color: rgba(0, 230, 118, 0.12);
    border: 1px solid #00e676;
    color: #00e676;
    font-weight: 700;
}

QPushButton#buyBtn:hover {
    background-color: rgba(0, 230, 118, 0.28);
}

/* Danger Button */
QPushButton#sellBtn {
    background-color: rgba(255, 82, 82, 0.12);
    border: 1px solid #ff5252;
    color: #ff5252;
    font-weight: 700;
}

QPushButton#sellBtn:hover {
    background-color: rgba(255, 82, 82, 0.28);
}

/* Inputs */
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background-color: #0b0f14;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 8px;
    color: #f0f6fc;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 12px;
}

QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border: 1px solid #58a6ff;
}

/* Sliders */
QSlider::groove:horizontal {
    border: 1px solid #262c36;
    height: 6px;
    background: #0b0f14;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #1f6feb;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #58a6ff;
    border: 1px solid #79c0ff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #79c0ff;
}

/* Tables */
QTableWidget {
    background-color: #0b0f14;
    border: 1px solid #262c36;
    border-radius: 6px;
    gridline-color: #1c2128;
    color: #c9d1d9;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    selection-background-color: rgba(88, 166, 255, 0.2);
}

QHeaderView::section {
    background-color: #131820;
    border: none;
    border-bottom: 1px solid #262c36;
    padding: 6px 8px;
    font-weight: 700;
    color: #8b949e;
    font-size: 11px;
    text-transform: uppercase;
}

QSplitter::handle {
    background-color: #262c36;
    width: 2px;
}

QScrollBar:vertical {
    border: none;
    background: #0b0f14;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #30363d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #8b949e;
}
"""
