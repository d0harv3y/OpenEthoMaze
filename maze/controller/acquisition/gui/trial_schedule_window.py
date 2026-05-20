"""Modeless trial schedule editor (task-generic slot preview + per-slot exits)."""

from __future__ import annotations

from typing import Callable

from ....core.session_slots import slot_to_animal_trial
from ..shared_config import ensure_exit_schedule_indices_length
from ..task_registry import AcquisitionMode, get_task_spec
from ..vast.arena import latin_square_exit_index
from ..shared_config import AcquisitionConfig

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TrialScheduleWindow(QDialog):
    """Preview slot order and edit per-slot exits when seed mode is manual."""

    def __init__(
        self,
        config: AcquisitionConfig,
        parent: QWidget,
        *,
        task_mode: AcquisitionMode,
        session_id_fn: Callable[[], str],
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._task_mode = task_mode
        self._task_spec = get_task_spec(task_mode)
        self._session_id_fn = session_id_fn
        self._apply_ok_by_parent = True
        self.setWindowTitle("Trial schedule")
        self.setWindowModality(Qt.WindowModality.NonModal)

        layout = QVBoxLayout(self)
        title_row = QHBoxLayout()
        self._session_label = QLabel("Session:—")

        title_row.addWidget(self._session_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        nav = QHBoxLayout()
        self._slot_label = QLabel("Preview slot: 0")
        nav.addWidget(self._slot_label)
        self._prev_btn = QPushButton("Prev")
        self._next_btn = QPushButton("Next")
        self._prev_btn.clicked.connect(self._on_prev)
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._next_btn)
        nav.addStretch()
        layout.addLayout(nav)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Index", "Animal ID", "Trial", "Exit"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        self._preview_slot = 0
        self._has_unsaved_edits = False

        actions = QHBoxLayout()
        self._fill_selected_btn = QPushButton("Fill selected with default")
        self._fill_selected_btn.clicked.connect(self._on_fill_selected_default)
        actions.addWidget(self._fill_selected_btn)
        self._fill_all_btn = QPushButton("Fill all with default")
        self._fill_all_btn.clicked.connect(self._on_fill_all_default)
        actions.addWidget(self._fill_all_btn)
        actions.addStretch()
        layout.addLayout(actions)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        self._apply_btn = bbox.button(QDialogButtonBox.StandardButton.Apply)
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setDefault(True)
        self._apply_btn.setAutoDefault(True)
        bbox.rejected.connect(self.close)
        layout.addWidget(bbox)

        self.refresh_from_config()

    def set_apply_enabled(self, enabled: bool) -> None:
        """Enable Apply for manual seed unless disabled by parent (e.g. trial running)."""
        self._apply_ok_by_parent = bool(enabled)
        self._sync_apply_enabled()

    def _sync_apply_enabled(self) -> None:
        man = self._config.session.seed_mode == "manual"
        self._apply_btn.setEnabled(bool(man and self._apply_ok_by_parent))
        self._fill_selected_btn.setEnabled(bool(man and self._apply_ok_by_parent))
        self._fill_all_btn.setEnabled(bool(man and self._apply_ok_by_parent))
        if not self._apply_ok_by_parent:
            self._apply_btn.setToolTip("Apply is disabled while a trial is running.")
        elif not man:
            self._apply_btn.setToolTip(
                "Switch session seed to â€œmanualâ€ in Settings to edit exits here."
            )
        else:
            self._apply_btn.setToolTip(
                "Write manual exit indices from the table into the session config."
            )

    def refresh_from_config(self) -> None:
        """Reload the table from ``self._config`` (e.g. after Settings or profile apply)."""
        if self._has_unsaved_edits and not self._confirm_discard_unsaved_edits():
            return
        self._has_unsaved_edits = False
        self._refresh_table()

    def _on_prev(self) -> None:
        self._preview_slot = max(0, self._preview_slot - 1)
        self._refresh_table()

    def _on_next(self) -> None:
        c = self._config
        n_a = max(0, c.session.num_animals)
        n_t = max(0, c.session.num_trials)
        total = max(0, n_a * n_t)
        if total > 0:
            self._preview_slot = min(total - 1, self._preview_slot + 1)
        self._refresh_table()

    def _refresh_table(self) -> None:
        c = self._config
        sid = (self._session_id_fn() or "").strip()
        self._session_label.setText(f"Session: {sid or 'â€”'}")
        n_a = max(0, c.session.num_animals)
        n_t = max(0, c.session.num_trials)
        total = max(0, n_a * n_t)
        man = c.session.seed_mode == "manual"
        n_ang = max(1, int(self._task_spec.get_num_exits(c)))
        default_i = max(0, min(n_ang - 1, int(self._task_spec.get_default_exit_index(c))))
        if man:
            ensure_exit_schedule_indices_length(
                c.session,
                n_exits=n_ang,
                default_exit_index=default_i,
            )
        mode = self._task_spec.get_mode_value(c)
        self._preview_slot = max(0, min(max(0, total - 1), self._preview_slot))
        self._slot_label.setText(f"Preview slot: {self._preview_slot}")
        self._table.setRowCount(total)
        self._table.blockSignals(True)
        for slot in range(total):
            aidx, tidx = slot_to_animal_trial(slot, n_a, n_t, mode)
            c.session.ensure_animals()
            animals = c.session.animals
            aid = (
                str(animals[aidx % max(1, len(animals))].animal_id) if animals else str(1000 + aidx)
            )
            self._table.setItem(slot, 0, QTableWidgetItem(str(slot)))
            self._table.setItem(slot, 1, QTableWidgetItem(aid))
            self._table.setItem(slot, 2, QTableWidgetItem(f"T{tidx + 1:02d}"))
            if (
                man
                and c.session.exit_schedule_indices
                and slot < len(c.session.exit_schedule_indices)
            ):
                exit_1 = int(c.session.exit_schedule_indices[slot]) + 1
            elif man:
                exit_1 = int(default_i) + 1
            else:
                seed_v = c.session.seed_auto_value
                ex0 = latin_square_exit_index(sid or "S", tidx, n_ang, seed_v)
                exit_1 = ex0 + 1
            it = QTableWidgetItem(str(exit_1))
            if man:
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(slot, 3, it)
        self._table.blockSignals(False)
        self._set_dirty(False)

        self._sync_apply_enabled()

    def _set_dirty(self, dirty: bool) -> None:
        self._has_unsaved_edits = bool(dirty)
        base = "Trial schedule"
        self.setWindowTitle(f"{base} *" if self._has_unsaved_edits else base)

    def _confirm_discard_unsaved_edits(self) -> bool:
        r = QMessageBox.question(
            self,
            "Discard unsaved schedule edits?",
            "You have unsaved Trial schedule edits. Discard them and reload from config?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return r == QMessageBox.StandardButton.Discard

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 3:
            return
        self._set_dirty(True)

    def _default_exit_1_based(self) -> int:
        c = self._config
        n_ang = max(1, int(self._task_spec.get_num_exits(c)))
        default_i = max(0, min(n_ang - 1, int(self._task_spec.get_default_exit_index(c))))
        return default_i + 1

    def _set_exit_text(self, row: int, value_1_based: int) -> None:
        it = self._table.item(row, 3)
        if it is None:
            it = QTableWidgetItem(str(value_1_based))
            self._table.setItem(row, 3, it)
            return
        it.setText(str(value_1_based))

    def _on_fill_all_default(self) -> None:
        if self._config.session.seed_mode != "manual":
            return
        d = self._default_exit_1_based()
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            self._set_exit_text(row, d)
        self._table.blockSignals(False)
        self._set_dirty(True)

    def _on_fill_selected_default(self) -> None:
        if self._config.session.seed_mode != "manual":
            return
        d = self._default_exit_1_based()
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if not rows:
            return
        self._table.blockSignals(True)
        for row in rows:
            self._set_exit_text(row, d)
        self._table.blockSignals(False)
        self._set_dirty(True)

    def _write_schedule_exit_indices_from_table(self) -> None:
        c = self._config
        if c.session.seed_mode != "manual":
            return
        n_ang = max(1, int(self._task_spec.get_num_exits(c)))
        total = max(0, c.session.num_animals * c.session.num_trials)
        out: list[int] = []
        for slot in range(total):
            it = self._table.item(slot, 3)
            raw = (it.text() if it is not None else "1").strip()
            try:
                v1 = int(raw)
            except ValueError:
                v1 = 1
            v1 = max(1, min(n_ang, v1))
            out.append(v1 - 1)
        c.session.exit_schedule_indices = out

    def _on_apply(self) -> None:
        c = self._config
        if c.session.seed_mode == "manual":
            ensure_exit_schedule_indices_length(
                c.session,
                n_exits=self._task_spec.get_num_exits(c),
                default_exit_index=self._task_spec.get_default_exit_index(c),
            )
            self._write_schedule_exit_indices_from_table()
            self._set_dirty(False)
        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_config_to_ui"):
            parent._apply_config_to_ui()
        if parent is not None and hasattr(parent, "statusBar") and parent.statusBar() is not None:
            parent.statusBar().showMessage("Trial schedule applied.")

    def closeEvent(self, event) -> None:
        if self._has_unsaved_edits and not self._confirm_discard_unsaved_edits():
            event.ignore()
            return
        super().closeEvent(event)
