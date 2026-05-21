"""Pipeline → QC summary dialog (Phase C8)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..shared_config import AcquisitionConfig

try:
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    from maze.pipeline.qc_summary import (
        collect_qc_summary,
        export_qc_mistrial_csv,
        format_qc_summary_text,
    )

    HAS_QC_SUMMARY_DIALOG = True
except ImportError:
    HAS_QC_SUMMARY_DIALOG = False


def _default_results_h5(config: "AcquisitionConfig") -> Path:
    out = (config.output_dir or "").strip()
    name = (config.h5_filename or "trials.h5").strip() or "trials.h5"
    if Path(name).name != name:
        name = Path(name).name
    return Path(out) / name if out else Path(name)


def _parse_filter_list(text: str) -> Optional[str]:
    s = text.strip()
    return s if s else None


if HAS_QC_SUMMARY_DIALOG:

    def open_qc_summary_dialog(parent: QWidget, config: "AcquisitionConfig") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Pipeline — QC summary")
        lay = QVBoxLayout(dlg)

        hint = QLabel(
            "Summarize mistrial reasons and analyze coverage for a results H5. "
            "Use after Analyze… to see which trials need fixes before export or kpMS. "
            "Export writes mistrial_summary.csv with action hints."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        h5_edit = QLineEdit(str(_default_results_h5(config)))
        fa = QLineEdit()
        fs = QLineEdit()
        ft = QLineEdit()
        fa.setPlaceholderText("Optional animal IDs")
        fs.setPlaceholderText("Optional sessions")
        ft.setPlaceholderText("Optional trials")

        def browse_h5() -> None:
            start = h5_edit.text().strip() or (config.output_dir or "")
            p, _ = QFileDialog.getOpenFileName(
                dlg, "Results HDF5", start, "HDF5 (*.h5 *.hdf5);;All (*)"
            )
            if p:
                h5_edit.setText(p)

        h5_row = QWidget()
        h5_h = QHBoxLayout(h5_row)
        h5_h.setContentsMargins(0, 0, 0, 0)
        h5_h.addWidget(h5_edit)
        h5_h.addWidget(QPushButton("Browse…", clicked=browse_h5))
        form.addRow("Results H5:", h5_row)
        form.addRow("Animal filter:", fa)
        form.addRow("Session filter:", fs)
        form.addRow("Trial filter:", ft)
        lay.addLayout(form)

        stats = QPlainTextEdit()
        stats.setReadOnly(True)
        stats.setMinimumHeight(100)
        lay.addWidget(stats)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Animal", "Session", "Trial", "Reason", "Suggested fix"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumHeight(180)
        lay.addWidget(table)

        last_summary = {"obj": None}

        def refresh() -> None:
            path = Path(h5_edit.text().strip())
            if not path.is_file():
                QMessageBox.warning(dlg, "QC summary", f"H5 not found: {path}")
                return
            try:
                summary = collect_qc_summary(
                    path,
                    animal_ids=_parse_filter_list(fa.text()),
                    sessions=_parse_filter_list(fs.text()),
                    trial_names=_parse_filter_list(ft.text()),
                )
            except Exception as e:
                QMessageBox.warning(dlg, "QC summary", f"{type(e).__name__}: {e}")
                return
            last_summary["obj"] = summary
            stats.setPlainText(format_qc_summary_text(summary))
            table.setRowCount(len(summary.mistrial_rows))
            for i, row in enumerate(summary.mistrial_rows):
                table.setItem(i, 0, QTableWidgetItem(row.animal_id))
                table.setItem(i, 1, QTableWidgetItem(row.session))
                table.setItem(i, 2, QTableWidgetItem(row.trial))
                table.setItem(i, 3, QTableWidgetItem(row.mistrial_reason))
                table.setItem(i, 4, QTableWidgetItem(row.action_hint))
            table.resizeColumnsToContents()

        def export_csv() -> None:
            summary = last_summary["obj"]
            if summary is None:
                QMessageBox.information(dlg, "QC summary", "Refresh summary first.")
                return
            out_dir = QFileDialog.getExistingDirectory(
                dlg,
                "Export folder",
                str(summary.db_path.parent / "exports"),
            )
            if not out_dir:
                return
            out = Path(out_dir)
            try:
                path = export_qc_mistrial_csv(summary, out / "mistrial_summary.csv")
            except Exception as e:
                QMessageBox.warning(dlg, "QC summary", f"{type(e).__name__}: {e}")
                return
            QMessageBox.information(dlg, "QC summary", f"Wrote:\n{path}")

        def open_exports_folder() -> None:
            summary = last_summary["obj"]
            folder = (
                summary.db_path.parent / "exports"
                if summary is not None
                else Path(h5_edit.text().strip()).parent / "exports"
            )
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)

        btn_row = QWidget()
        btn_h = QHBoxLayout(btn_row)
        btn_h.setContentsMargins(0, 0, 0, 0)
        btn_h.addWidget(QPushButton("Refresh", clicked=refresh))
        btn_h.addWidget(QPushButton("Export mistrial CSV…", clicked=export_csv))
        btn_h.addWidget(QPushButton("Open exports folder", clicked=open_exports_folder))
        lay.addWidget(btn_row)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(720, 520)
        dlg.show()
        refresh()

else:

    def open_qc_summary_dialog(parent: object, config: object) -> None:
        del parent, config
