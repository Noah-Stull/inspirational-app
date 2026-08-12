"""Entry point for the Inspirational App."""

import sys

from PyQt6.QtWidgets import QApplication

from app.core.config import APP_NAME
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
