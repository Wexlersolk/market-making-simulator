"""Dark Institutional Styling & QSS Themes for MMSim Desktop GUI."""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #0d1117;
    color: #e6edf3;
}

QWidget {
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
    color: #c9d1d9;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #30363d;
    background: #161b22;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background: #0d1117;
    border: 1px solid #30363d;
    border-bottom: none;
    padding: 10px 22px;
    margin-right: 4px;
    font-weight: 600;
    color: #8b949e;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #161b22;
    color: #58a6ff;
    border-color: #30363d;
    border-top: 2px solid #58a6ff;
}

QTabBar::tab:hover {
    color: #f0f6fc;
}

/* Group Boxes / Cards */
QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px;
    font-weight: 700;
    color: #58a6ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
}

/* Push Buttons */
QPushButton {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    color: #c9d1d9;
}

QPushButton:hover {
    background-color: #30363d;
    color: #f0f6fc;
    border-color: #8b949e;
}

QPushButton:pressed {
    background-color: #161b22;
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
    background-color: rgba(0, 230, 118, 0.15);
    border: 1px solid #00e676;
    color: #00e676;
    font-weight: 700;
}

QPushButton#buyBtn:hover {
    background-color: rgba(0, 230, 118, 0.35);
}

/* Danger Button */
QPushButton#sellBtn {
    background-color: rgba(255, 23, 68, 0.15);
    border: 1px solid #ff1744;
    color: #ff1744;
    font-weight: 700;
}

QPushButton#sellBtn:hover {
    background-color: rgba(255, 23, 68, 0.35);
}

/* Inputs */
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f0f6fc;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
}

QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border: 1px solid #58a6ff;
}

/* Tables */
QTableWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    gridline-color: #21262d;
    color: #c9d1d9;
    font-family: 'JetBrains Mono', monospace;
}

QHeaderView::section {
    background-color: #161b22;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 6px 8px;
    font-weight: 700;
    color: #8b949e;
    font-size: 11px;
    text-transform: uppercase;
}

QScrollBar:vertical {
    border: none;
    background: #0d1117;
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
