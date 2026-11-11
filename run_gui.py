#!/usr/bin/env python3
"""Launcher for Apex Market Making & Derivatives Station Desktop GUI.

Usage:
    python run_gui.py
"""
import sys
from pathlib import Path

# Add src to sys.path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from mmsim.gui.app import main

if __name__ == "__main__":
    main()
