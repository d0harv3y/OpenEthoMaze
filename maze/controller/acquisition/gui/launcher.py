"""Qt entrypoint for acquisition GUI (kept out of ``app_shell`` to avoid import cycles)."""

from __future__ import annotations

import sys
from typing import Literal

from .. import app_logging

AcquisitionMode = Literal["vast", "ram"]


def _load_mode_window_factory(mode: AcquisitionMode):
    if mode == "ram":
        from .main_window import (
            DEFAULT_WINDOW_SIZE,
            HAS_QT,
            QT_ERROR_MESSAGE,
            build_window,
        )

        def build_ram_window(*, dev: bool = False):
            return build_window(dev=dev, task_mode="ram")

        return HAS_QT, QT_ERROR_MESSAGE, build_ram_window, DEFAULT_WINDOW_SIZE

    from .main_window import (
        DEFAULT_WINDOW_SIZE,
        HAS_QT,
        QT_ERROR_MESSAGE,
        build_window,
    )

    def build_vast_window(*, dev: bool = False):
        return build_window(dev=dev, task_mode="vast")

    return HAS_QT, QT_ERROR_MESSAGE, build_vast_window, DEFAULT_WINDOW_SIZE


def run_mode_gui(
    mode: AcquisitionMode,
    *,
    debug_log: bool = False,
    dev: bool = False,
) -> int:
    has_qt, qt_error_message, build_window, window_size = _load_mode_window_factory(mode)
    if not has_qt:
        print(qt_error_message)
        return 1

    from PySide6.QtWidgets import QApplication

    app_logging.init_app_logging(debug_log=debug_log)
    app = QApplication(sys.argv)
    window = build_window(dev=dev)
    width, height = window_size
    window.resize(width, height)
    window.show()
    return app.exec()
