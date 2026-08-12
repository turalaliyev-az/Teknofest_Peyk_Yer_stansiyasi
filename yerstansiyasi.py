#!/usr/bin/env python3
"""Teknofest Yer İstasyonu — giriş noktası.

Çalıştırma:
    python3 yerstansiyasi.py
"""
from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from gs.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Teknofest Yer İstasyonu")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
