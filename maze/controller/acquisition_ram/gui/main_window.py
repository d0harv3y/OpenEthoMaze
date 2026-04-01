from __future__ import annotations

import sys
from pathlib import Path

from ..config import RadialArmControllerConfig
from ...acquisition.h5_writer import init_database

try:
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    HAS_QT = True
except ImportError:
    HAS_QT = False


if HAS_QT:
    class MainWindow(QMainWindow):
        """Small scaffold window for the future radial-arm acquisition GUI."""

        def __init__(self) -> None:
            super().__init__()
            self._config = RadialArmControllerConfig()
            self.setWindowTitle("Maze RAM Acquisition")

            root = QWidget(self)
            self.setCentralWidget(root)
            layout = QVBoxLayout(root)
            layout.addWidget(
                QLabel(
                    "Radial-arm acquisition is scaffolded here so RAM can share the "
                    "maze package, H5 schema, and downstream pipeline hooks."
                )
            )

            row = QHBoxLayout()
            self._output_edit = QLineEdit()
            self._output_edit.setPlaceholderText("Output folder")
            browse_btn = QPushButton("Browse…")
            browse_btn.clicked.connect(self._on_browse_output)
            row.addWidget(self._output_edit)
            row.addWidget(browse_btn)
            layout.addLayout(row)

            init_btn = QPushButton("Initialize RAM DB")
            init_btn.clicked.connect(self._on_initialize_db)
            layout.addWidget(init_btn)

            layout.addWidget(
                QLabel(
                    "Current scope: write RAM-tagged metadata and reserve a dedicated "
                    "entrypoint. The full state machine and hardware UI can now land "
                    "under maze.controller.acquisition_ram without touching the VAST UI."
                )
            )

        def _on_browse_output(self) -> None:
            output_dir = QFileDialog.getExistingDirectory(self, "Select RAM output folder")
            if output_dir:
                self._output_edit.setText(output_dir)

        def _on_initialize_db(self) -> None:
            output_dir = self._output_edit.text().strip()
            if not output_dir:
                self.statusBar().showMessage("Choose an output folder first.")
                return
            self._config.output_dir = output_dir
            db_path = Path(output_dir) / self._config.h5_filename
            init_database(db_path, arena_type=self._config.arena_type)
            self.statusBar().showMessage(f"Initialized RAM database: {db_path}")


def run_gui() -> int:
    if not HAS_QT:
        print("PySide6 is required for the RAM GUI.")
        return 1
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(520, 220)
    win.show()
    return app.exec()
