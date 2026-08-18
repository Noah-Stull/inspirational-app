"""Entry point for the Inspirational App."""

import logging
import sys

from PyQt6.QtWidgets import QApplication

from app.core.config import APP_NAME
from app.ui.main_window import MainWindow


def main() -> int:
    # Without this, log.info about which data source won is discarded and
    # only warnings reach stderr.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
