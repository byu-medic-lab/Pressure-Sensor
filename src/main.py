"""Application entry point."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app.controller import AppController
from app.config import AppConfig
from gui.main_window import MainWindow


def main() -> int:
    """Start the PyQt application in simulation mode by default."""
    app = QApplication(sys.argv)
    config = AppConfig(simulation_mode=True)
    controller = AppController(config=config)
    window = MainWindow(controller=controller)
    controller.set_window(window)
    window.showMaximized()
    exit_code = app.exec()
    controller.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
